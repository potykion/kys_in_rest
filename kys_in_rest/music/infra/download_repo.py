import glob
import os
import shlex
import subprocess
import tempfile

import mutagen
from PIL import Image

from kys_in_rest.core.musicbrainz import MusicBrainzClient
from kys_in_rest.core.path_utils import do_in_dir
from kys_in_rest.music.features.download_repo import DownloadRepo
from kys_in_rest.tg.entities.audio import TgAudio


class YandexMusicDownloadRepo(DownloadRepo):
    """
    https://github.com/llistochek/yandex-music-downloader
    """

    def __init__(self, yandex_music_token: str) -> None:
        self.yandex_music_token = yandex_music_token

    def download_audio_from_url(
        self,
        url: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TgAudio]:
        with tempfile.TemporaryDirectory() as temp_dir:
            with do_in_dir(temp_dir):
                command = " ".join(
                    [
                        "yandex-music-downloader",
                        "--token",
                        shlex.quote(self.yandex_music_token),
                        "--quality",
                        "1",
                        "--skip-existing",
                        "--url",
                        shlex.quote(url),
                    ]
                )
                subprocess.call(
                    command,
                    text=True,
                    shell=True,
                )
                mp3 = [
                    *glob.glob("./**/*.mp3", recursive=True),
                    *glob.glob("./**/*.m4a", recursive=True),
                ][0]
                cover = glob.glob("./**/cover.*", recursive=True)[0]
                if cover.endswith(".png"):
                    with Image.open(cover) as img:
                        rgb_img = img.convert("RGB")

                        cover_jpg = os.path.splitext(cover)[0] + ".jpg"
                        rgb_img.save(cover_jpg, "JPEG")
                else:
                    cover_jpg = cover

                with open(mp3, "rb") as mp3_file:
                    with open(cover_jpg, "rb") as cover_f:
                        audio = mp3_file.read()

                        audio_file = mutagen.File(mp3)

                        title = (
                            audio_file.get("TIT2")
                            or audio_file.get("\xa9nam")
                            or audio_file.get("TITLE", [None])
                        )[0]

                        artist = (
                            audio_file.get("TPE1")
                            or audio_file.get("\xa9ART")
                            or audio_file.get("ARTIST", [None])
                        )[0]
                        artist = artist.replace(";", ",")

                        duration = (
                            int(audio_file.info.length)
                            if hasattr(audio_file, "info")
                            else 0
                        )

                        cover_bytes = cover_f.read()
                        return [
                            TgAudio(
                                audio=audio,
                                artist=artist,
                                title=title,
                                cover=cover_bytes,
                                duration=duration,
                            )
                        ]


class YouTubeDownloadRepo(DownloadRepo):
    """
    https://github.com/yt-dlp/yt-dlp/
    """

    def __init__(self, musicbrainz_client: MusicBrainzClient = None):
        self.musicbrainz_client = musicbrainz_client or MusicBrainzClient()

    def download_audio_from_url(
        self,
        url: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TgAudio]:
        url = self.clean_url(url)

        with tempfile.TemporaryDirectory() as temp_dir:
            with do_in_dir(temp_dir):
                command = [
                    "yt-dlp",
                    "-x",
                    *("--audio-format", "mp3"),
                    "--split-chapters",
                    url,
                ]
                subprocess.call(
                    command,
                    text=True,
                    shell=True,
                )
                mp3s = [
                    *glob.glob("./**/*.mp3", recursive=True),
                    *glob.glob("./**/*.m4a", recursive=True),
                    *glob.glob("./**/*.opus", recursive=True),
                ]

                # Удаляем самый большой файл
                if mp3s:
                    largest_file = max(mp3s, key=os.path.getsize)
                    os.remove(largest_file)
                    mp3s.remove(largest_file)

                audios = []
                cover_bytes = None
                for mp3 in mp3s:
                    # Извлекаем artist и title из имени файла
                    artist, album, title = self.parse_meta(os.path.basename(mp3))

                    with open(mp3, "rb") as mp3_file:
                        audio = mp3_file.read()

                        audio_file = mutagen.File(mp3)

                        duration = (
                            int(audio_file.info.length)
                            if hasattr(audio_file, "info")
                            else 0
                        )

                        # Получаем обложку через MusicBrainzClient
                        cover_bytes = (
                            cover_bytes
                            or self.musicbrainz_client.get_cover_by_artist_album(
                                artist, album
                            )
                        )

                        audios.append(
                            TgAudio(
                                audio=audio,
                                artist=artist,
                                title=title,
                                duration=duration,
                                cover=cover_bytes,
                            )
                        )
                return audios

    @classmethod
    def clean_url(cls, url: str) -> str:
        """
        >>> YouTubeDownloadRepo.clean_url("https://www.youtube.com/watch?v=QpcbCqSUkcM&t=889s")
        'https://www.youtube.com/watch?v=QpcbCqSUkcM'
        """
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # Удаляем параметр 't' (timestamp)
        if "t" in query_params:
            del query_params["t"]

        # Перестраиваем query string
        new_query = urlencode(query_params, doseq=True)

        # Создаем новый URL без параметра timestamp
        cleaned_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )

        return cleaned_url

    @classmethod
    def parse_meta(
        cls, filename: str
    ) -> tuple[str, str, str] | tuple[None, None, None]:
        """
        Парсит имя файла YouTube для извлечения artist, album и title.

        Примеры:
        >>> YouTubeDownloadRepo.parse_meta("KFC Murder Chicks - KFCMC (Full Album) - 001 Dune [QpcbCqSUkcM].mp3")
        ('KFC Murder Chicks', 'KFCMC', 'Dune')
        """
        import re

        # Убираем расширение файла
        name_without_ext = os.path.splitext(filename)[0]

        # Убираем ID видео в квадратных скобках
        name_without_id = re.sub(r"\s*\[[^\]]+\]\s*$", "", name_without_ext)

        # Ищем паттерн "Artist - Album - Number Title"
        match = re.match(r"^(.+?)\s*-\s*(.+?)\s*-\s*\d+\s+(.+)$", name_without_id)

        if match:
            artist = match.group(1).strip()
            album = match.group(2).strip()
            title = match.group(3).strip()
            # Очищаем название альбома
            album = clean_album(album)
            return artist, album, title

        # Если не удалось распарсить, возвращаем None
        return None, None, None


def clean_album(album: str) -> str:
    """
    >>> clean_album("KFCMC (Full Album)")
    'KFCMC'
    """
    import re

    # Удаляем все скобки и их содержимое
    cleaned = re.sub(r"\s*\([^)]*\)", "", album)
    return cleaned.strip()


class UrlDownloadRepo(DownloadRepo):
    def __init__(
        self,
        yandex_music_download_repo: YandexMusicDownloadRepo,
        youtube_download_repo: YouTubeDownloadRepo,
    ):
        self.yandex_music_download_repo = yandex_music_download_repo
        self.youtube_download_repo = youtube_download_repo

    def download_audio_from_url(
        self,
        url: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TgAudio]:
        if url.startswith("https://music.yandex.ru"):
            return self.yandex_music_download_repo.download_audio_from_url(url)
        if url.startswith("https://www.youtube.com"):
            return self.youtube_download_repo.download_audio_from_url(url)
        else:
            raise Exception(f"Unsupported {url=}")
