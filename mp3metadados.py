import flet as ft
from datetime import datetime
import subprocess
import os
import json
import platform
from flet import DataTable, DataColumn, DataRow, DataCell, Text

def get_audio_metadata(file_path):
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if result.returncode != 0:
            return {"error": result.stderr}
        metadata = json.loads(result.stdout)
        
        return metadata
    except Exception as e:
        return {"error": str(e)}

def update_audio_metadata(file_path, new_metadata, output_path, audio_filters=None):
    try:
        cmd = ['ffmpeg', '-i', file_path]
        
        if audio_filters:
            print(f"Aplicando filtros de áudio: {audio_filters}") 
            cmd.extend(['-af', audio_filters])
        for key, value in new_metadata.items():
            cmd.extend(['-metadata', f'{key}={value}'])
            print(f"Adicionando metadado: {key}={value}")  
        
        cmd.extend([
            '-c:a', 'libmp3lame',    
            '-b:a', '320k',          
            '-ar', '48000',          
            '-q:a', '0',             
            output_path
        ])
        print(f"Re-encodificando com libmp3lame para: {output_path}")
        
        print(f"Comando FFmpeg: {' '.join(cmd)}")
        
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        if process.returncode != 0:
            print(f"Erro no FFmpeg: {process.stderr}")
            return f"Erro: {process.stderr}"
        print("Processo concluído com sucesso.")
        return "Metadados e conteúdo atualizados com sucesso."
    except Exception as e:
        print(f"Exceção: {str(e)}")
        return f"Erro ao atualizar metadados: {str(e)}"

def open_folder(file_path):
    folder = os.path.dirname(file_path)
    if platform.system() == "Windows":
        os.startfile(folder)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])

def generate_output_path(file_path, suffix="_edited"):
    base, ext = os.path.splitext(file_path)
    return f"{base}{suffix}{ext}"

def main(page: ft.Page):
    page.title = "Editor de Metadados de Áudios MP3"
    page.window.width = 1400
    page.window.height = 900
    page.padding = 20
    page.spacing = 20
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    selected_files = []
    metadata_fields = {}
    audio_filters_field = {}
    metadata_display = ft.Column(scroll='auto')
    output_message = ft.Text("Selecione um ou mais arquivos MP3 para editar os metadados.", size=14)
    output_card = ft.Card(
        content=ft.Container(
            content=output_message,
            padding=10,
            border_radius=ft.border_radius.all(10),
            bgcolor=ft.colors.GREY_100,
            alignment=ft.alignment.center
        ),
        elevation=3,
        margin=ft.margin.only(top=10)
    )
    METADATA_FIELDS = [
        ("title", "Nome da Música"),
        ("artist", "Artista"),
        ("album", "Nome do Álbum"),
        ("genre", "Gênero"),
        ("date", "Ano"),
        ("track", "Número da Faixa"),
        ("comment", "Comentário"),
        ("lyrics", "Letra")
    ]

    def on_files_upload(e):
        nonlocal selected_files
        try:
            if e.files:
                selected_files = []
                metadata_display.controls.clear()

                for file in e.files:
                    file_path = file.path
                    if not file_path.lower().endswith('.mp3'):
                        output_message.value = f"Arquivo {os.path.basename(file_path)} não é um MP3 válido."
                        print(f"Arquivo inválido: {file_path}")
                        continue

                    metadata = get_audio_metadata(file_path)
                    if "error" in metadata:
                        output_message.value = f"Erro ao extrair metadados de {os.path.basename(file_path)}: {metadata['error']}"
                        print(f"Erro de metadata: {metadata['error']}")
                        continue

                    selected_files.append(file_path)

                    fields = {}
                    format_tags = metadata.get('format', {}).get('tags', {})
                    format_properties = {k: v for k, v in metadata.get('format', {}).items() if k not in [
                        'tags', 'filename', 'nb_streams', 'nb_programs', 'format_long_name',
                        'start_time', 'duration', 'size', 'bit_rate', 'probe_score']}
                    
                    all_format_tags = format_tags.copy()
                    for prop, value in format_properties.items():
                        all_format_tags[prop] = value
                    for tag, label in METADATA_FIELDS:
                        value = all_format_tags.get(tag, "")
                        if tag == "lyrics":
                            fields[tag] = ft.TextField(
                                label=label,
                                value=str(value),
                                width=600,
                                multiline=True,
                                min_lines=3,
                                max_lines=10
                            )
                        else:
                            fields[tag] = ft.TextField(
                                label=label,
                                value=str(value),
                                width=400
                            )
                    audio_filters_field[file_path] = ft.TextField(
                        label="Filtros de Áudio (FFmpeg)",
                        hint_text="Exemplo: atempo=1.25,volume=0.8",
                        width=600
                    )
                    metadata_display.controls.append(
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Text(f"Arquivo: {os.path.basename(file_path)}", size=16, weight=ft.FontWeight.BOLD),
                                    *[fields[tag] for tag, _ in METADATA_FIELDS],
                                    audio_filters_field[file_path]
                                ], spacing=10),
                                padding=10,
                                border_radius=ft.border_radius.all(10),
                                bgcolor=ft.colors.WHITE,
                            ),
                            elevation=3,
                            margin=ft.margin.only(bottom=20)
                        )
                    )
                    metadata_fields[file_path] = fields

                if selected_files:
                    output_message.value = f"{len(selected_files)} arquivo(s) selecionado(s) para edição."
                    print(f"Arquivos selecionados: {selected_files}")
                else:
                    output_message.value = "Nenhum arquivo válido selecionado."
                    print("Nenhum arquivo válido selecionado.")

                update_buttons()
                page.update()
            else:
                output_message.value = "Nenhum arquivo selecionado."
                update_buttons()
                page.update()
                print("Nenhum arquivo selecionado.")
        except Exception as err:
            output_message.value = f"Erro ao processar os arquivos: {str(err)}"
            print(f"Erro na função on_files_upload: {str(err)}")
            page.update()

    def save_metadata(e):
        try:
            if not selected_files:
                output_message.value = "Nenhum arquivo selecionado para salvar."
                page.update()
                print("Nenhum arquivo selecionado para salvar.")
                return

            for file_path in selected_files:
                fields = metadata_fields.get(file_path, {})
                new_metadata = {}

                for tag, _ in METADATA_FIELDS:
                    field = fields.get(tag)
                    if field and field.value.strip():
                        new_metadata[tag] = field.value.strip()

                audio_filters = audio_filters_field[file_path].value.strip()
                audio_filters = audio_filters if audio_filters else None

                output_path = generate_output_path(file_path)

                result = update_audio_metadata(
                    file_path,
                    new_metadata,
                    output_path,
                    audio_filters=audio_filters
                )
                output_message.value = result
                print(f"Resultado da atualização: {result}")

            page.update()
        except Exception as err:
            output_message.value = f"Erro ao salvar metadados: {str(err)}"
            print(f"Erro na função save_metadata: {str(err)}")
            page.update()

    def show_metadata(e):
        print("Botão 'Mostrar Metadados' clicado.")
        try:
            if not selected_files:
                output_message.value = "Nenhum arquivo selecionado para mostrar metadados."
                page.update()
                print("Nenhum arquivo selecionado.")
                return

            metadata_info = ft.Column(scroll=ft.ScrollMode.AUTO)
            print(f"Arquivos selecionados: {selected_files}") 

            for file_path in selected_files:
                print(f"Processando arquivo: {file_path}")  
                metadata = get_audio_metadata(file_path)
                if "error" in metadata:
                    metadata_info.controls.append(
                        ft.Text(
                            f"Erro em {os.path.basename(file_path)}: {metadata['error']}",
                            color=ft.colors.RED
                        )
                    )
                    print(f"Erro ao extrair metadados: {metadata['error']}") 
                    continue

                # Metadados de Formato
                format_info = metadata.get('format', {})
                format_tags = format_info.get('tags', {})
                format_properties = {k: v for k, v in format_info.items() if k not in [
                    'tags', 'filename', 'nb_streams', 'nb_programs', 'format_long_name',
                    'start_time', 'duration', 'size', 'bit_rate', 'probe_score'
                ]}
                print(f"Metadados de formato: {format_info}") 

                all_format_tags = format_tags.copy()
                for prop, value in format_properties.items():
                    all_format_tags[prop] = value

                format_table = ft.DataTable(
                    columns=[
                        DataColumn(Text("Campo")),
                        DataColumn(Text("Valor"))
                    ],
                    rows=[
                        DataRow(cells=[
                            DataCell(Text(k.capitalize())),
                            DataCell(Text(v))
                        ]) for k, v in sorted(all_format_tags.items())
                    ]
                )
                print("Tabela de metadados de formato criada.") 

                streams = metadata.get('streams', [])
                stream_tables = []
                for idx, stream in enumerate(streams):
                    codec_type = stream.get('codec_type', 'Unknown').capitalize()
                    stream_tags = stream.get('tags', {})
                    stream_properties = {k: v for k, v in stream.items() if k not in [
                        'tags', 'index', 'codec_name', 'codec_type', 'codec_long_name',
                        'profile', 'codec_time_base', 'codec_tag_string', 'codec_tag',
                        'sample_fmt', 'sample_rate', 'channels', 'channel_layout',
                        'bits_per_sample', 'bits_per_raw_sample', 'r_frame_rate',
                        'avg_frame_rate', 'time_base', 'start_pts', 'start_time',
                        'duration_ts', 'duration', 'bit_rate', 'max_bit_rate',
                        'nb_frames', 'disposition', 'tags'
                    ]}
                    print(f"Processando stream {idx + 1}: {codec_type}") 

                    all_stream_tags = stream_tags.copy()
                    for prop, value in stream_properties.items():
                        all_stream_tags[prop] = value

                    stream_table = ft.DataTable(
                        columns=[
                            DataColumn(Text("Campo")),
                            DataColumn(Text("Valor"))
                        ],
                        rows=[
                            DataRow(cells=[
                                DataCell(Text(k.capitalize())),
                                DataCell(Text(v))
                            ]) for k, v in sorted(all_stream_tags.items())
                        ]
                    )
                    print(f"Tabela de metadados de stream {idx + 1} criada.") 

                    # Adiciona a tabela com título para cada stream
                    stream_tables.append(
                        ft.Column([
                            ft.Text(f"Stream {idx + 1}: {codec_type}", size=14, weight=ft.FontWeight.BOLD),
                            stream_table
                        ], spacing=5)
                    )

                metadata_info.controls.append(
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text(f"Arquivo: {os.path.basename(file_path)}", size=16, weight=ft.FontWeight.BOLD),
                                ft.Text("Metadados de Formato:", size=14, weight=ft.FontWeight.BOLD),
                                format_table,
                                ft.Text("Metadados de Streams:", size=14, weight=ft.FontWeight.BOLD),
                                *stream_tables
                            ], spacing=10),
                            padding=10,
                            border_radius=ft.border_radius.all(10),
                            bgcolor=ft.colors.WHITE,
                        ),
                        elevation=2,
                        margin=ft.margin.only(bottom=15)
                    )
                )
                print(f"Metadados adicionados para {file_path}") 

            metadata_dialog.content = ft.Container(
                content=metadata_info,
                width=1200,
                height=700
            )
            metadata_dialog.open = True
            page.update()
            print("Diálogo de metadados aberto.") 
        except Exception as err:
            output_message.value = f"Erro ao mostrar metadados: {str(err)}"
            print(f"Erro na função show_metadata: {str(err)}")  
            page.update()

    def close_metadata_dialog(e, dialog):
        dialog.open = False
        page.update()
        print("Diálogo de metadados fechado.")  

    file_picker = ft.FilePicker(on_result=on_files_upload)
    page.overlay.append(file_picker)

    pick_button = ft.ElevatedButton(
        "Selecionar Áudios MP3",
        icon=ft.icons.MUSIC_NOTE,
        on_click=lambda _: file_picker.pick_files(
            allow_multiple=True,
            file_type=ft.FilePickerFileType.AUDIO
        )
    )
    save_button = ft.ElevatedButton(
        "Salvar Metadados e Alterar Conteúdo",
        icon=ft.icons.SAVE,
        on_click=save_metadata,
        disabled=True
    )
    show_metadata_button = ft.ElevatedButton(
        "Mostrar Metadados",
        icon=ft.icons.INFO,
        on_click=show_metadata,
        disabled=True
    )
    open_folder_button = ft.ElevatedButton(
        "Abrir Pasta do Arquivo",
        icon=ft.icons.FOLDER_OPEN,
        on_click=lambda e: open_folder(selected_files[0]) if selected_files else None,
        disabled=True
    )
    def update_buttons():
        if selected_files:
            save_button.disabled = False
            show_metadata_button.disabled = False
            open_folder_button.disabled = False
        else:
            save_button.disabled = True
            show_metadata_button.disabled = True
            open_folder_button.disabled = True
        page.update()
        print("Botões atualizados.")

    metadata_dialog = ft.AlertDialog(
        title=ft.Text("Metadados dos Arquivos MP3"),
        content=ft.Container(),
        actions=[
            ft.TextButton("Fechar", on_click=lambda e: close_metadata_dialog(e, metadata_dialog))
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        modal=True
    )
    page.overlay.append(metadata_dialog)

    page.add(
        ft.Row(
            controls=[pick_button, save_button, show_metadata_button, open_folder_button],
            spacing=10,
            alignment=ft.MainAxisAlignment.START
        ),
        metadata_display,
        output_card
    )
ft.app(target=main)
