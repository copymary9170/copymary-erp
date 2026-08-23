from src.marketing_story_video import video_readiness_score


def test_video_readiness_score_complete():
    row = {
        "strategy": "ventas", "intention": "confianza", "narrative": "caso real",
        "structure": "hook-desarrollo-cta", "retention": "cortes", "editing": "subtitulos"
    }
    assert video_readiness_score(row) == 100


def test_video_readiness_score_partial():
    assert video_readiness_score({"strategy": "alcance", "intention": "curiosidad"}) < 100
