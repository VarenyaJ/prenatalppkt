# Setup

`prenatalppkt` is a Python library for turning prenatal ultrasound data into
GA4GH Phenopacket v2 objects.

Most users run it in one of three ways:

1. From the test suite.
2. From `prenatalppkt.ipynb`.
3. From a short Python command or script.

The package targets Python 3.10 or later.

## Clone the repository

```bash
git clone https://github.com/VarenyaJ/prenatalppkt.git
cd prenatalppkt
```

Use the active development branch unless you were told to use another branch:

```bash
git checkout vj/develop
```

## Option 1 - install with plain venv

Use this path if you prefer standard Python tools.

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Check the install:

```bash
python -c "import prenatalppkt; print(prenatalppkt.__version__)"
pytest tests/builders/test_observer_phenopacket.py
```

When you come back later:

```bash
cd prenatalppkt
source .venv/bin/activate
```

## Option 2 - install with uv

Use this path if you already use `uv`.

```bash
uv sync --frozen --extra dev
```

Check the install:

```bash
uv run python -c "import prenatalppkt; print(prenatalppkt.__version__)"
uv run pytest tests/builders/test_observer_phenopacket.py
```

Use `--frozen` so the versions in `uv.lock` are respected.

## Run the tests

Run the full test suite:

```bash
pytest
```

Run a smaller smoke test:

```bash
pytest tests/etl/extractors/test_observer.py
pytest tests/builders/test_observer_phenopacket.py
```

With `uv`, prefix commands with `uv run`:

```bash
uv run pytest
uv run pytest tests/etl/extractors/test_observer.py
uv run pytest tests/builders/test_observer_phenopacket.py
```

Useful focused tests:

| Area | Command |
|---|---|
| HPO mapping | `pytest tests/test_mapping_loader.py tests/test_term_bin.py` |
| Observer extractor | `pytest tests/etl/extractors/test_observer.py` |
| Clinical section parsers | `pytest tests/etl/sections` |
| Phenopacket builder | `pytest tests/builders/test_observer_phenopacket.py` |
| HPO recognizer | `pytest tests/hpo` |
| Genomics scaffold | `pytest tests/genomics` |
| Data dictionary tools | `pytest src/prenatalppkt/scripts/data_dict/tests` |

Stop on the first failure:

```bash
pytest -x
```

Run one test by name:

```bash
pytest tests/builders/test_observer_phenopacket.py::test_apple_sally_real_fixture_smoke
```

## Dependency pins

Do not casually upgrade these packages:

| Package | Version | Why it matters |
|---|---:|---|
| `phenopackets` | `2.0.2.post5` | GA4GH Phenopacket v2 Python classes |
| `protobuf` | `3.20.3` | Compatible with `phenopackets` 2.x |
| `hpo-toolkit` | `0.5.5` | HPO loading and ontology access |
| `pyphetools` | `0.9.118` | Still present on `vj/develop` until the Fenominal migration lands |

If a dependency must change, run the full test suite before accepting the
change.

## Open the notebook

The notebook shows the whole pipeline in a visible, step-by-step way.

With plain `venv`:

```bash
source .venv/bin/activate
pip install jupyter
jupyter lab prenatalppkt.ipynb
```

With `uv`:

```bash
uv run jupyter lab prenatalppkt.ipynb
```

The notebook does four main things:

1. Loads a fixture HPO ontology.
2. Loads an Observer JSON fixture.
3. Extracts measurements and report sections.
4. Builds and serializes a Phenopacket.

## Run the library from the terminal

`prenatalppkt` is mainly a library right now. The most reliable terminal path
is to run a short Python script.

### Build a Phenopacket from an Observer fixture

With plain `venv`:

```bash
python - <<'PY'
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from google.protobuf.json_format import MessageToJson
from google.protobuf.timestamp_pb2 import Timestamp

from prenatalppkt.builders import build_observer_phenopacket
from prenatalppkt.hpo import HpoParser

hp_gz = Path("tests/data/hp.json.gz")
hp_json = Path("/tmp/hp.json")

with gzip.open(hp_gz, "rt", encoding="utf-8") as src:
    hp_json.write_text(src.read())

hpo_parser = HpoParser(hpo_json_file=str(hp_json))
observer_data = json.loads(Path("tests/data/Apple_Sally_pretty.json").read_text())

created = Timestamp()
created.FromDatetime(datetime.now(timezone.utc))

phenopackets = build_observer_phenopacket(
    observer_data,
    hpo_parser,
    created,
    accession_id="apple-sally",
)

print(f"built {len(phenopackets)} phenopacket(s)")
print(MessageToJson(phenopackets[0], preserving_proto_field_name=True)[:1200])
PY
```

With `uv`:

```bash
uv run python - <<'PY'
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from google.protobuf.json_format import MessageToJson
from google.protobuf.timestamp_pb2 import Timestamp

from prenatalppkt.builders import build_observer_phenopacket
from prenatalppkt.hpo import HpoParser

hp_gz = Path("tests/data/hp.json.gz")
hp_json = Path("/tmp/hp.json")

with gzip.open(hp_gz, "rt", encoding="utf-8") as src:
    hp_json.write_text(src.read())

hpo_parser = HpoParser(hpo_json_file=str(hp_json))
observer_data = json.loads(Path("tests/data/Apple_Sally_pretty.json").read_text())

created = Timestamp()
created.FromDatetime(datetime.now(timezone.utc))

phenopackets = build_observer_phenopacket(
    observer_data,
    hpo_parser,
    created,
    accession_id="apple-sally",
)

print(f"built {len(phenopackets)} phenopacket(s)")
print(MessageToJson(phenopackets[0], preserving_proto_field_name=True)[:1200])
PY
```

### Extract Observer biometry only

```bash
python - <<'PY'
import json
from pathlib import Path

from prenatalppkt.etl.extractors import observer

data = json.loads(Path("tests/data/Apple_Sally_pretty.json").read_text())
term_bins = observer.extract(data)

for term_bin in term_bins:
    print(term_bin.description, term_bin.hpo_id, term_bin.hpo_label)
PY
```

With `uv`, use:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

from prenatalppkt.etl.extractors import observer

data = json.loads(Path("tests/data/Apple_Sally_pretty.json").read_text())
term_bins = observer.extract(data)

for term_bin in term_bins:
    print(term_bin.description, term_bin.hpo_id, term_bin.hpo_label)
PY
```

## Build the docs locally

With plain `venv`:

```bash
source .venv/bin/activate
pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

With `uv`:

```bash
uv run --extra docs sphinx-build -b html docs docs/_build/html
```

Then open:

```text
docs/_build/html/index.html
```

For Read the Docs, the build configuration lives in:

```text
.readthedocs.yaml
docs/conf.py
```

## Make a docs or code change

Create a branch:

```bash
git checkout vj/develop
git pull
git checkout -b vj/my-change
```

Edit files, then inspect the change:

```bash
git status
git diff
```

Run tests:

```bash
pytest
```

For docs-only changes, also run:

```bash
sphinx-build -b html docs docs/_build/html
```

Commit:

```bash
git add docs/setup.md
git commit -m "docs: refresh setup guide"
```

Push:

```bash
git push -u origin vj/my-change
```

Open a pull request on GitHub.
