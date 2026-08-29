import re

from nltk.tokenize import sent_tokenize

# Acronyms are matched on word boundaries. Plain str.replace() mangles anything
# that merely CONTAINS the token: the AITAH variant became "Am I the A-holeH"
# on screen, and a bare "AH" rule would turn "AHEAD" into "A-holeEAD".
# Longest variants first so AITAH is consumed before AITA can match it.
acronyms = [
    (r"\bAITAH\b", "Am I the A-hole"),
    (r"\bAITA\b", "Am I the A-hole"),
    (r"\bWIBTAH\b", "Would I be the A-hole"),
    (r"\bWIBTA\b", "Would I be the A-hole"),
    (r"\bAH\b", "A-hole"),
    (r"\bMIL\b", "mother-in-law"),
    (r"\bmil\b", "mother-in-law"),
]

synonyms = [
    ("Asshole", "A-hole"),
    ("asshole", "A-hole"),
    ("fuck", "frick"),
    ("fucking", "fricking")
]


def clean_up_text(text):
    for (pattern, replacement) in acronyms:
        text = re.sub(pattern, replacement, text)
    for (original, replacement) in synonyms:
        text = text.replace(original, replacement)
    return text


def inside_parenthesis(text):
    return "(" in text and not ")" in text


def uppercase_age(text):
    return re.sub("(\([0-9]+ ?)([mf])(\s*\))", lambda match: r'{}{}{}'.format(match.group(1).upper(), match.group(2).upper(), match.group(3).upper()), text)


def is_edit(sentence):
    sentence = sentence.lower()
    return "edit" in sentence or "update" in sentence or sentence.startswith("eta")


def split_and_correct_text(text):
    text = re.sub(r" but ", ", but ", text)
    text = re.sub(r" and ", ", and ", text)
    text = re.sub(r" or ", ", or ", text)
    text = re.sub(r"\*", " - ", text)
    text = re.sub(r" \'", "'", text)

    text = re.sub("\s+", " ", text)
    text = re.sub("\.+", ".", text)
    text = re.sub(",+", ",", text)
    sentences = sent_tokenize(".".join(text.split("\n")))

    for sentence in sentences:
        if is_edit(sentence):
            break
        corrected = sentence.strip()
        corrected = uppercase_age(corrected)
        if len(corrected.split()) < 25:
            yield corrected
            continue
        split = re.split(r"(,)", corrected)
        result = []
        for phrase in split:
            phrase = phrase.strip()
            result.append(phrase)

            if phrase == ",":
                if len(" ".join(result).split(" ")) > 15 and not inside_parenthesis(" ".join(result)):
                    yield(" ".join(result).replace(" ,", ","))
                    result = []

        if result:
            yield(" ".join(result).replace(" ,", ","))


def find_gender(text):
    gender = re.search("(?:my|i)\s*\([0-9]*([mf])[0-9]*\)", text.lower())
    if gender is not None:
        if gender.group(1).lower().startswith("m"):
            return 'male'
        return 'female'

    if "my girlfriend" in text:
        return "male"

    return 'female'


if __name__ == '__main__':
    text = '''
    Example text\n
    Spread over multiple lines, and such AITA and they sometimes use alot of phrases chained together and stuff.
    not always having commas and some speling erors.
    Ok. 'fix this too please. '
    'For the past few months I (17m) haven’t had a good relationship with my mom or stepdad. '

    EDIT: this edit should be removed. And this should not be visible
    '''

    for line in split_and_correct_text(clean_up_text(text)):
        print(line)

    genders = [
        "I (M35) have 2 sisters that I'm close with, I also have a niece (Leah), Leah's 16 and after my ex wife decided to split up and divorce due to inferitility problems that lasted for 5 years. I started a college fund for Leah to help her go to her chosen college. ",
        "my (M35) have 2 sisters that I'm close with, I also have a niece (Leah), Leah's 16 and after my ex wife decided to split up and divorce due to inferitility problems that lasted for 5 years. I started a college fund for Leah to help her go to her chosen college. ",
        "My(M35) have 2 sisters that I'm close with, I also have a niece (Leah), Leah's 16 and after my ex wife decided to split up and divorce due to inferitility problems that lasted for 5 years. I started a college fund for Leah to help her go to her chosen college. ",
        "My(f35) have 2 sisters that I'm close with, I also have a niece (Leah), Leah's 16 and after my ex wife decided to split up and divorce due to inferitility problems that lasted for 5 years. I started a college fund for Leah to help her go to her chosen college. ",
        "My (F35) have 2 sisters that I'm close with, I also have a niece (Leah), Leah's 16 and after my ex wife decided to split up and divorce due to inferitility problems that lasted for 5 years. I started a college fund for Leah to help her go to her chosen college. ",
    ]
    for line in genders:
        print(find_gender(line))
