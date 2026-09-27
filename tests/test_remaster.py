from nfsu_tools.movies.remaster import RemasterConfig, build_filter_chain


def test_build_filter_chain_letterboxed_auto() -> None:
    # 16:9 letterbox with 32px bars in 512x256 frame -> should crop to 512x192 and scale to 3840x2160
    cfg = RemasterConfig(
        target_resolution=(3840, 2160),
        aspect_mode="auto",
        crop_letterbox=True,
        sharpening="cas",
        sharpening_strength=0.4,
    )
    vf = build_filter_chain(cfg, is_letterboxed=True, top_bar=32, bot_bar=32)

    assert "crop=512:192:0:32" in vf
    assert "scale=3840:2160:flags=lanczos+accurate_rnd" in vf
    assert "cas=0.40" in vf


def test_build_filter_chain_full_frame_auto() -> None:
    # Full 4:3 frame (e.g. logo) -> should scale to 2880x2160 and pad to 3840x2160
    cfg = RemasterConfig(
        target_resolution=(3840, 2160),
        aspect_mode="auto",
        crop_letterbox=True,
        sharpening="unsharp",
    )
    vf = build_filter_chain(cfg, is_letterboxed=False, top_bar=0, bot_bar=0)

    assert "scale=2880:2160" in vf
    assert "pad=3840:2160:480:0:black" in vf
    assert "unsharp=" in vf


def test_build_filter_chain_explicit_16_9() -> None:
    cfg = RemasterConfig(
        target_resolution=(1920, 1080),
        aspect_mode="16:9",
        crop_letterbox=False,
        sharpening="none",
    )
    vf = build_filter_chain(cfg, is_letterboxed=True, top_bar=32, bot_bar=32)

    assert "scale=1920:1080" in vf
    assert "crop" not in vf
    assert "cas" not in vf
