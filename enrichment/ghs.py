"""GHS hazard statement utilities — shared across all iil repos.

Provides:
- H_STATEMENTS_DE: H-code → German description mapping
- h_codes_to_descriptions(): Convert H-code set to human-readable list
"""

from __future__ import annotations

# GHS H-Statement codes → German descriptions (GHS Rev. 10)
H_STATEMENTS_DE: dict[str, str] = {
    "H200": "Instabil, explosiv",
    "H201": "Explosiv; Gefahr der Massenexplosion",
    "H202": "Explosiv; große Gefahr durch Splitter",
    "H220": "Extrem entzündbares Gas",
    "H221": "Entzündbares Gas",
    "H224": "Flüssigkeit und Dampf extrem entzündbar",
    "H225": "Flüssigkeit und Dampf leicht entzündbar",
    "H226": "Flüssigkeit und Dampf entzündbar",
    "H228": "Entzündbarer Feststoff",
    "H242": "Erwärmung kann Brand verursachen",
    "H270": "Kann Brand verursachen oder verstärken; Oxidationsmittel",
    "H271": "Kann Brand oder Explosion verursachen; starkes Oxidationsmittel",
    "H272": "Kann Brand verstärken; Oxidationsmittel",
    "H280": "Enthält Gas unter Druck",
    "H281": "Enthält tiefgekühltes Gas",
    "H290": "Kann gegenüber Metallen korrosiv sein",
    "H300": "Lebensgefahr bei Verschlucken",
    "H301": "Giftig bei Verschlucken",
    "H302": "Gesundheitsschädlich bei Verschlucken",
    "H304": "Kann bei Verschlucken und Eindringen in die Atemwege tödlich sein",
    "H310": "Lebensgefahr bei Hautkontakt",
    "H311": "Giftig bei Hautkontakt",
    "H312": "Gesundheitsschädlich bei Hautkontakt",
    "H314": "Verursacht schwere Verätzungen der Haut und schwere Augenschäden",
    "H315": "Verursacht Hautreizungen",
    "H317": "Kann allergische Hautreaktionen verursachen",
    "H318": "Verursacht schwere Augenschäden",
    "H319": "Verursacht schwere Augenreizung",
    "H330": "Lebensgefahr bei Einatmen",
    "H331": "Giftig bei Einatmen",
    "H332": "Gesundheitsschädlich bei Einatmen",
    "H334": "Kann bei Einatmen Allergie oder Asthma auslösen",
    "H335": "Kann die Atemwege reizen",
    "H336": "Kann Schläfrigkeit und Benommenheit verursachen",
    "H340": "Kann genetische Defekte verursachen",
    "H341": "Kann vermutlich genetische Defekte verursachen",
    "H350": "Kann Krebs erzeugen",
    "H351": "Kann vermutlich Krebs erzeugen",
    "H360": "Kann die Fruchtbarkeit beeinträchtigen oder das Kind im Mutterleib schädigen",
    "H361": "Kann vermutlich die Fruchtbarkeit beeinträchtigen oder das Kind schädigen",
    "H362": "Kann Säuglinge über die Muttermilch schädigen",
    "H370": "Schädigt die Organe",
    "H371": "Kann die Organe schädigen",
    "H372": "Schädigt die Organe bei längerer oder wiederholter Exposition",
    "H373": "Kann die Organe schädigen bei längerer oder wiederholter Exposition",
    "H400": "Sehr giftig für Wasserorganismen",
    "H410": "Sehr giftig für Wasserorganismen mit langfristiger Wirkung",
    "H411": "Giftig für Wasserorganismen mit langfristiger Wirkung",
    "H412": "Schädlich für Wasserorganismen mit langfristiger Wirkung",
    "H413": "Kann für Wasserorganismen schädlich sein mit langfristiger Wirkung",
    "H420": "Schädigt die öffentliche Gesundheit und die Umwelt durch Ozonabbau",
}


def h_codes_to_descriptions(h_codes: set[str] | list[str]) -> list[str]:
    """Map H-codes to German descriptions.

    Returns sorted list of "H-code: description" strings.
    Unknown codes are silently skipped.
    """
    descriptions: list[str] = []
    for code in sorted(h_codes):
        desc = H_STATEMENTS_DE.get(code, "")
        if desc:
            descriptions.append(f"{code}: {desc}")
    return descriptions
