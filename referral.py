"""Single source of truth for the Tilt Rips referral code.

The code used to be written out twice - once in autopost.py's caption PROMO and
once, letter-spaced for the text-to-speech outro, in generate-assets/run.py.
They drifted: captions said UL2IYH9M while every video said "J T M O T J C J"
out loud. Viewers who acted on the spoken code credited a different one, which
is the most likely reason referrals dried up.

Both the caption and the narration now derive from CODE below, so a change in
one place cannot leave the other stale.
"""

# MASTER SWITCH. False = no referral text in captions or narration at all.
#
# Turned OFF 2026-09-13. The offer is a deposit match for a sweepstakes casino,
# and TikTok restricts gambling promotion - it was riding on all 88 posts, in the
# caption and (since 2026-08-29) spoken aloud at the end of every video. That is
# the most plausible explanation for views pinned at 100-200 with occasional
# breakouts, which is what restricted-content damping looks like. It also blocks
# the TikTok Shop pivot outright: Shop affiliate and an off-platform gambling
# offer cannot coexist on the same account.
#
# Set back to True to restore it everywhere; nothing else needs changing.
ENABLED = False

# The referral code itself. Change it HERE and nowhere else.
CODE = "UL2IYH9M"

# What the offer actually is, kept next to the code so the two stay consistent.
OFFER = "deposit $10 and get a FREE $10 pack"

# Where viewers are sent. TikTok does not make captions clickable, so the link
# has to live in the profile bio - captions point at it with "link in bio".
# Empty until Kaleb supplies the real referral URL.
LINK = ""


def spoken_code(code=CODE):
    """Letter-spaced so the TTS reads it out rather than mangling it as a word.

    "UL2IYH9M" -> "U L 2 I Y H 9 M"
    """
    return " ".join(code)


def spoken_offer(code=CODE):
    """The outro sentence, with the code spelled out for narration.

    Returns "" while ENABLED is False, so run.py's outro simply ends after the
    follow prompt instead of reading a gambling offer aloud.
    """
    if not ENABLED:
        return ""
    return ("And if you rip cards, use code %s on Tilt Rips - "
            "deposit ten dollars and get a free ten dollar pack."
            % spoken_code(code))


def end_card(code=CODE):
    """The promo box drawn on the video's end card, or None while ENABLED is False.

    This used to be hardcoded in video-generator/src/Video.tsx, where it kept showing
    the dead code JTMOTJCJ on every end card even after ENABLED was switched off on
    2026-09-13. run.py now writes this into script.json and Video.tsx only draws what
    it is given, so all three places (caption, narration, end card) share one switch.
    """
    if not ENABLED:
        return None
    return {"headline": "🎁 Code %s on Tilt Rips" % code, "sub": "Deposit $10 → FREE $10 pack"}


def caption_promo(code=CODE, link=LINK):
    """The caption line. Mentions the bio link only once there is one.

    Returns "" while ENABLED is False. Callers must drop empty parts rather than
    joining blindly, or the caption gains a blank paragraph where this used to be.
    """
    if not ENABLED:
        return ""
    base = "\U0001F381 Use code %s on Tilt Rips — %s" % (code, OFFER)
    if link:
        base += " — link in bio"
    return base
