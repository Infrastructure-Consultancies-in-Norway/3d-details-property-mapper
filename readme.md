# 3d-details-property-mapper

Legger SNACKS-egenskapssett med eksempelverdier direkte på elementforekomster i
IFC-filer. Verktøyet bruker IfcOpenShell og endrer ikke geometri eller originale
inputfiler.

## Oppsett

Prosjektet krever Python 3.12 på Windows.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Den lokale `.venv`-mappen er ignorert av Git.

## Kjøring

Legg IFC-filer i `ifc-files/input` og kjør:

```powershell
.\.venv\Scripts\snacks-ifc.exe
```

Ferdige filer skrives med samme filnavn til `ifc-files/output`. Inputfilene blir
liggende uendret. Test mappingen uten å skrive filer med:

```powershell
.\.venv\Scripts\snacks-ifc.exe --dry-run
```

En enkelt fil og en annen output kan angis eksplisitt:

```powershell
.\.venv\Scripts\snacks-ifc.exe `
	--input .\ifc-files\input\modell.ifc `
	--output .\ifc-files\output\modell.ifc
```

## Mapping

Reglene ligger i `config/mapping.yaml` og matcher dekodet IFC-elementnavn med
case-insensitive regex.

Alle `IfcElement`-forekomster unntatt `Ramme` får som utgangspunkt:

- `BIM_Tverrfaglig`
- `KON_Felles`

Følgende navn får i tillegg et fagsett:

| Navn | Egenskapssett |
| --- | --- |
| `Løsmasser_1`, `Løsmasser_2` | `KON_Løsmasser` |
| `Armering_Rustfritt` | `KON_Armering` |
| `Landkar`, `Overgangsplate` | `KON_Betong` |

En regel kan fjerne et basissett med `exclude_property_sets`. Løsmasser beholder
`BIM_Tverrfaglig`, men får `KON_Løsmasser` i stedet for `KON_Felles`:

```yaml
- id: loose-materials
	name_pattern: '^Løsmasser_[12]$'
	property_sets:
		- KON_Løsmasser
	exclude_property_sets:
		- KON_Felles
```

Objekter som asfalt, fuktisolering, kleber og rissanvisende fuge får foreløpig
bare de to felles settene fordi SNACKS-katalogen ikke har passende fagsett for
disse.

Verdier kan overstyres i samme konfigurasjon. `default_values` gjelder alle
elementer som får det angitte basissettet, mens `rules[].values` bare gjelder
elementer som matcher regelen. En regelverdi vinner over en standardverdi:

```yaml
default_values:
	KON_Felles:
		'KON.30 - Plasseringsprioritet': '2 - Virker for 1'

rules:
	- id: transition-slab
		name_pattern: '^Overgangsplate$'
		property_sets:
			- KON_Betong
		values:
			KON_Felles:
				'KON.10 - Konstruksjonsinndeling': Underbygning
				'KON.11 - Konstruksjonsdel': Landkar
				'KON.13 - Elementnavn': Overgangsplate
```

Egenskapssettet må være tilordnet som basissett eller av den aktuelle regelen.
Egenskapsnavn og datatype valideres mot den låste SNACKS-katalogen før IFC-modellen
endres. Egenskaper uten YAML-verdi bruker fortsatt katalogens fallbackverdi.

## SNACKS-katalog

Katalogen lastes fra SnacksDto release `0.1.0-alpha` og caches i
`.cache/snacks-0.1.0-alpha.json`. Verktøyet godtar bare filen med den låste
SHA-256-verdien:

```text
33f4601aa617c63323a87fc8a508328bd3fa118cb4520fa728df064cdbe8020d
```

En lokal, identisk katalogfil kan angis med `--catalog`. Bare svarte,
obligatoriske egenskaper brukes. Grå, valgfrie egenskaper hoppes over. Verdien
velges i denne rekkefølgen:

1. `SampleValue`
2. første `RecommendedValues`
3. første `AllowedValues`

Kjøringen stopper før IFC-endring dersom et obligatorisk felt mangler verdi,
katalogen har feil checksum eller konfigurasjonen er ugyldig.

## Oppdatering og validering

Eksisterende direkte SNACKS-sett oppdateres. De dupliseres ikke ved gjentatt
kjøring. Typebaserte egenskapssett regnes ikke som direkte occurrence-sett.

Output skrives først til en midlertidig fil, åpnes på nytt og valideres før den
erstatter endelig output. For eksempelmodellen forventes:

| Egenskapssett | Antall elementer |
| --- | ---: |
| `BIM_Tverrfaglig` | 18 |
| `KON_Felles` | 15 |
| `KON_Løsmasser` | 3 |
| `KON_Armering` | 1 |
| `KON_Betong` | 2 |

## Utvikling

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```
