import os
from flask import Flask, render_template, request, jsonify, send_from_directory
import librosa
import numpy as np
import logging
import yt_dlp
import re
import unicodedata
import joblib  

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Limite de 100MB


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class YTDLPLogger(object):
    def debug(self, msg):
        logger.debug(msg)
    
    def info(self, msg):
        logger.info(msg)
    
    def warning(self, msg):
        logger.warning(msg)
    
    def error(self, msg):
        logger.error(msg)
    
    def critical(self, msg):
        logger.critical(msg)

def sanitize_filename(name):
    """
    Sanitiza o nome do arquivo removendo caracteres inválidos.
    """
    name = unicodedata.normalize('NFKC', name)
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    return sanitized

def detect_key(y, sr):
    """
    Detecta a tonalidade e escala da música usando a biblioteca librosa.
    """
    chromagram = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = np.mean(chromagram, axis=1)
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F',
             'F#', 'G', 'G#', 'A', 'A#', 'B']
    max_note = chroma_mean.argmax()
    key = notes[max_note]

    if max_note in [0, 5, 7]:  # C, F, G
        scale = 'Major'
    else:
        scale = 'Minor'

    key_full = f'{key} {scale}'

    alt_note = (max_note + 9) % 12  # Relativo menor/maior
    alt_scale = 'Minor' if scale == 'Major' else 'Major'
    alt_key_full = f'{notes[alt_note]} {alt_scale}'

    return key_full, alt_key_full

def detect_genre(y, sr):
    """
    Detecta o gênero musical usando um modelo pré-treinado.
    """
    try:
        if not genre_model:
            return 'Unknown'
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
        mfccs_mean = np.mean(mfccs.T, axis=0)
        
        genre_prediction = genre_model.predict([mfccs_mean])
        return genre_prediction[0]
    except Exception as e:
        logger.exception('Erro durante a detecção de gênero.')
        return 'Unknown'

def convert_to_serializable(obj):
    """
    Converte objetos NumPy para tipos nativos do Python para serialização JSON.
    """
    if isinstance(obj, (np.float32, np.float64, float)):
        return float(obj)
    elif isinstance(obj, (np.int32, np.int64, int)):
        return int(obj)
    return obj

MODEL_PATH = 'genre_classifier.pkl'  
if os.path.exists(MODEL_PATH):
    genre_model = joblib.load(MODEL_PATH)
    logger.debug('Modelo de gênero carregado com sucesso.')
else:
    genre_model = None
    logger.warning('Modelo de gênero não encontrado. Gênero será definido como "Unknown".')

@app.route('/')
def index():
    """
    Rota principal que renderiza a página inicial.
    """
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Rota para analisar arquivos de música enviados pelo usuário.
    """
    if 'music_file' not in request.files:
        logger.error('Nenhum arquivo enviado.')
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400

    file = request.files['music_file']

    if file.filename == '':
        logger.error('Nenhum arquivo selecionado.')
        return jsonify({'error': 'Nenhum arquivo selecionado.'}), 400

    if file:
        filename = sanitize_filename(file.filename)  
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(filepath)
            logger.debug(f'Arquivo salvo em: {filepath}')

            try:
                y, sr = librosa.load(filepath, duration=60)
                logger.debug(f'Arquivo carregado: {filepath}')

                bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
                bpm = round(float(bpm), 2)
                logger.debug(f'BPM detectado: {bpm}')

                key, alt_key = detect_key(y, sr)
                logger.debug(f'Tonalidade detectada: {key}')
                logger.debug(f'Tonalidade alternativa detectada: {alt_key}')

                energy = round(float(np.mean(librosa.feature.rms(y=y))), 4)
                logger.debug(f'Energia: {energy}')

                onset_env = librosa.onset.onset_strength(y=y, sr=sr)
                danceability = round(float(np.mean(onset_env)), 4)
                logger.debug(f'Dançabilidade: {danceability}')

                genre = detect_genre(y, sr)
                logger.debug(f'Gênero detectado: {genre}')

                happiness = 'High' if 'Major' in key else 'Low'
                logger.debug(f'Happiness: {happiness}')

                prompt = (
                    f"key of {key}, BPM of {bpm}. "
                    f"energy {energy}, danceability {danceability}, Genre: {genre}"
                )
                logger.debug(f'Prompt gerado para Suno.ai: {prompt}')

                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.debug(f'Arquivo removido: {filepath}')
                else:
                    logger.warning(f'Arquivo não encontrado para remoção: {filepath}')

                return jsonify({
                    'Key': key,
                    'Alt Key': alt_key,
                    'BPM': bpm,
                    'Energy': energy,
                    'Danceability': danceability,
                    'Happiness': happiness,
                    'Genre': genre,
                    'Prompt': prompt
                })

            except Exception as e:
                logger.exception('Erro durante a análise do áudio.')
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.debug(f'Arquivo removido após erro: {filepath}')
                return jsonify({'error': f'Erro durante a análise do áudio: {str(e)}'}), 500

        except Exception as e:
            logger.exception('Erro ao salvar o arquivo.')
            return jsonify({'error': f'Erro ao salvar o arquivo: {str(e)}'}), 500

@app.route('/download', methods=['POST'])
def download():
    """
    Rota para baixar vídeos do YouTube como arquivos MP3.
    """
    data = request.get_json()
    if not data or 'youtube_url' not in data:
        logger.error('Nenhuma URL do YouTube enviada.')
        return jsonify({'error': 'Nenhuma URL do YouTube enviada.'}), 400

    youtube_url = data['youtube_url']
    logger.debug(f'URL recebida para download: {youtube_url}')

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(app.config['UPLOAD_FOLDER'], '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320', 
        }],
        'logger': YTDLPLogger(),
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_url, download=True)
            title = info_dict.get('title', None)
            if not title:
                logger.error('Título do vídeo não encontrado.')
                return jsonify({'error': 'Falha ao obter o título do vídeo.'}), 500

            ext = info_dict.get('ext', 'mp3')
            filename = f"{sanitize_filename(title)}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            files = os.listdir(app.config['UPLOAD_FOLDER'])
            logger.debug(f'Arquivos na pasta uploads após download: {files}')

            for file in files:
                if file.endswith('.mp3') and '｜' in file:
                    sanitized_file = sanitize_filename(file)
                    original_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
                    sanitized_path = os.path.join(app.config['UPLOAD_FOLDER'], sanitized_file)
                    try:
                        os.rename(original_path, sanitized_path)
                        logger.debug(f'Arquivo renomeado de {file} para {sanitized_file}')
                        filename = sanitized_file
                        filepath = sanitized_path
                    except Exception as rename_error:
                        logger.exception(f'Erro ao renomear arquivo: {rename_error}')
                        return jsonify({'error': 'Erro ao sanitizar o nome do arquivo.'}), 500
                    break

            if not os.path.exists(filepath):
                logger.error('Arquivo MP3 não foi criado.')
                return jsonify({'error': 'Falha ao baixar o MP3.'}), 500

            logger.debug(f'Arquivo MP3 baixado: {filepath}')
            return send_from_directory(directory=app.config['UPLOAD_FOLDER'],
                                       path=filename,
                                       as_attachment=True,
                                       mimetype='audio/mpeg')

    except yt_dlp.utils.DownloadError as e:
        logger.exception('Erro específico durante o download do YouTube.')
        return jsonify({'error': f'Erro específico durante o download do YouTube: {str(e)}'}), 500
    except Exception as e:
        logger.exception('Erro inesperado durante o download do YouTube.')
        return jsonify({'error': f'Erro inesperado durante o download do YouTube: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
