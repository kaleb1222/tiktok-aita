"""Single source of truth for the referral promo (caption, narration, end card).

History: the Tilt Rips code used to be written out in three places (autopost.py's
caption, run.py's spoken outro, and Video.tsx's end card). They drifted - captions
said UL2IYH9M while videos said and showed "JTMOTJCJ". Everything now derives from
the settings below, so a change here reaches all three.

2026-09-27: switched from Tilt Rips (they cut the referrer reward from a $10 pack to
a $1 pack per signup) to Crown Coins Casino, which is a link-only referral - there
is no code to say or show, so viewers are pointed at the link in the TikTok bio.
"""

# MASTER SWITCH. False = no referral text in captions, narration or the end card.
#
# Turned OFF 2026-09-13 and deliberately still off: both offers are sweepstakes
# casinos and TikTok restricts gambling promotion. Riding on every post, in the
# caption and spoken aloud, is the most plausible explanation for views pinned at
# 100-200, which is what restricted-content damping looks like. It also blocks the
# TikTok Shop pivot: Shop affiliate and an off-platform gambling offer cannot coexist.
# The link lives in the profile bio instead (see bio_nudge), which is neither in the
# video nor the caption.
#
# Set to True to restore it everywhere; nothing else needs changing.
ENABLED = False

NAME = "Crown Coins Casino"

# Link-only referral. None = nothing to say or show; viewers use the bio link.
CODE = None

# What a new player gets. Left empty until Kaleb says - never invent an offer.
OFFER = ""

# TikTok captions aren't clickable, so this belongs in the profile bio.
LINK = ("https://crowncoinscasino.com/?utm_campaign=967193f9-cd4e-4be0-914a-a55b00790dee"
        "&utm_source=friends")


def spoken_code(code=CODE):
    """Letter-spaced so the TTS reads it out rather than mangling it as a word."""
    return " ".join(code) if code else ""


def spoken_offer(code=CODE):
    """The outro sentence for narration. "" while ENABLED is False."""
    if not ENABLED:
        return ""
    if code:
        line = "And use code %s on %s." % (spoken_code(code), NAME)
    else:
        line = "And check out %s with the link in my bio." % NAME
    return line + (" " + OFFER[0].upper() + OFFER[1:] + "." if OFFER else "")


def end_card(code=CODE):
    """The promo box drawn on the video's end card, or None while ENABLED is False."""
    if not ENABLED:
        return None
    headline = ("\U0001F381 Code %s on %s" % (code, NAME)) if code else ("\U0001F381 %s — link in bio" % NAME)
    return {"headline": headline, "sub": OFFER[0].upper() + OFFER[1:] if OFFER else ""}


def bio_nudge():
    """A neutral line pointing at the profile, independent of ENABLED.

    The offer lives in the TikTok bio, the only clickable surface TikTok gives a
    creator, and the safest placement: restricted-content damping keys on what is in
    the video and the caption. So this deliberately names no casino, deposit or bonus -
    naming the offer here is exactly what ENABLED=False exists to avoid.
    """
    return "\U0001F517 more in bio"


def caption_promo(code=CODE, link=LINK):
    """The caption line. "" while ENABLED is False; callers drop empty parts."""
    if not ENABLED:
        return ""
    base = ("\U0001F381 Use code %s on %s" % (code, NAME)) if code else ("\U0001F381 %s" % NAME)
    if OFFER:
        base += " — " + OFFER
    if link:
        base += " — link in bio"
    return base
