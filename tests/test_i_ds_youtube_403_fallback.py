"""Regression for safe, separately named public YouTube 403 fallback."""
from pathlib import Path
import pytest
import stratum_download_studio as studio


URL = "https://www.youtube.com/watch?v=public_fixture"
JOB = "12345678" + "a" * 24


@pytest.mark.parametrize("error,url,template,allowed", [
    ("HTTP Error 403: Forbidden", URL, "source-12345678.%(ext)s", True),
    ("HTTP Error 403: Forbidden", "https://youtu.be/fixture", "source-12345678.%(ext)s", True),
    ("HTTP Error 403: Forbidden", "https://youtube.com.evil.example/", "source-12345678.%(ext)s", False),
    ("HTTP Error 403: Forbidden", "https://example.com/video", "source-12345678.%(ext)s", False),
    ("HTTP Error 404: Not Found", URL, "source-12345678.%(ext)s", False),
    ("HTTP Error 403: Forbidden", URL, "source-%(ext)s", False),
])
def test_guard_limits_client_retry(error,url,template,allowed):
    assert studio.should_retry_public_youtube_403(error,url,template,JOB) is allowed


def test_alternate_template_isolated_from_old_partials():
    original = "video [%(id)s]-12345678.%(ext)s"
    fallback = studio.alternate_youtube_output_template(original,JOB)
    assert fallback == "video [%(id)s]-android-12345678.%(ext)s"
    assert fallback != original
    with pytest.raises(ValueError):
        studio.alternate_youtube_output_template("video.%(ext)s",JOB)


def test_youtube_403_retries_once_with_isolated_android_client(tmp_path,monkeypatch):
    template = str(tmp_path / "file [%(id)s]-12345678.%(ext)s")
    final = tmp_path / "file [synthetic]-android-12345678.mp4"
    final.write_bytes(b"safe synthetic fixture bytes")
    attempts = []
    class YDL:
        def __init__(self,options):
            self.options = options
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def extract_info(self,url,download=False):
            attempts.append(self.options)
            if len(attempts)==1:
                raise RuntimeError("HTTP Error 403: Forbidden")
            assert self.options["extractor_args"]["youtube"]["player_client"]==["android"]
            assert self.options["outtmpl"].endswith("-android-12345678.%(ext)s")
            return {"filepath":str(final),"id":"synthetic"}
    monkeypatch.setattr(studio.yt_dlp,"YoutubeDL",YDL)
    monkeypatch.setattr(studio,"resolve_final_media",lambda *args,**kwargs: (final, {"streams":[{"codec_type":"video","codec_name":"h264"}]}))
    monkeypatch.setattr(studio,"profile_codecs_compatible",lambda *args,**kwargs: True)
    monkeypatch.setattr(studio,"cleanup_verified_intermediates",lambda *args,**kwargs: [])
    results=[]
    worker=studio.DownloadThread(JOB, URL, template, "", "MP4", save_dir=tmp_path)
    worker.finished.connect(lambda *args:results.append(args))
    worker.run()
    assert len(attempts)==2
    assert attempts[0]["outtmpl"]!=attempts[1]["outtmpl"]
    assert len(results)==1 and results[0][1] is True,results
    assert results[0][3]==str(final)


def test_no_retry_for_other_site_403(tmp_path,monkeypatch):
    attempts=[]
    class YDL:
        def __init__(self,options):pass
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def extract_info(self,url,download=False):
            attempts.append(url)
            raise RuntimeError("HTTP Error 403: Forbidden")
    monkeypatch.setattr(studio.yt_dlp,"YoutubeDL",YDL)
    results=[]
    worker=studio.DownloadThread(JOB,"https://example.com/v",str(tmp_path / "file-12345678.%(ext)s"),"","MP4",save_dir=tmp_path)
    worker.finished.connect(lambda *args:results.append(args))
    worker.run()
    assert len(attempts)==1
    assert results and results[0][1] is False
