import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QFileDialog, QVBoxLayout
import librosa
import numpy as np
import os

class MusicAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.title = 'Analisador de Música'
        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.title)

        self.layout = QVBoxLayout()

        self.label = QLabel('Selecione um arquivo de música', self)
        self.layout.addWidget(self.label)

        self.button = QPushButton('Selecionar Arquivo', self)
        self.button.clicked.connect(self.openFileNameDialog)
        self.layout.addWidget(self.button)

        self.result_label = QLabel('', self)
        self.layout.addWidget(self.result_label)

        self.setLayout(self.layout)

    def openFileNameDialog(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Selecione um arquivo de música", "",
                                                  "Arquivos de Áudio (*.mp3 *.wav *.flac *.ogg)", options=options)
        if fileName:
            self.label.setText(f'Arquivo selecionado: {os.path.basename(fileName)}')
            self.analyzeMusic(fileName)

    def analyzeMusic(self, file_path):
        
        y, sr = librosa.load(file_path, duration=60)  

        
        file_name = os.path.basename(file_path)

        
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo)

        
        key, alt_key = self.detect_key(y, sr)

        
        energy = np.mean(librosa.feature.rms(y=y)).item()

        
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        danceability = np.mean(onset_env).item()

        
        happiness = 'Alta' if 'Maior' in key else 'Baixa'

        
        result_text = f'''
<b>Nome do Arquivo:</b> {file_name}
<b>Tonalidade:</b> {key}
<b>Tonalidade Alternativa:</b> {alt_key}
<b>BPM:</b> {bpm:.2f}
<b>Energia:</b> {energy:.4f}
<b>Dançabilidade:</b> {danceability:.4f}
<b>Felicidade:</b> {happiness}
'''
        self.result_label.setText(result_text)
        self.result_label.setStyleSheet("font-size: 14px;")

    def detect_key(self, y, sr):
        
        chromagram = librosa.feature.chroma_cqt(y=y, sr=sr)
        
        chroma_mean = np.mean(chromagram, axis=1)
        
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F',
                 'F#', 'G', 'G#', 'A', 'A#', 'B']
        
        max_note = chroma_mean.argmax()
        key = notes[max_note]

        
        
        if max_note in [0, 5, 7]:  
            scale = 'Maior'
        else:
            scale = 'Menor'

        key_full = f'{key} {scale}'

        
        alt_note = (max_note + 9) % 12  
        alt_scale = 'Menor' if scale == 'Maior' else 'Maior'
        alt_key_full = f'{notes[alt_note]} {alt_scale}'

        return key_full, alt_key_full

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MusicAnalyzer()
    ex.show()
    sys.exit(app.exec_())
