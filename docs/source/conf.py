# Configuration file for the Oasis example-models documentation.
#
# This docs project hosts worked, executable examples that run the Oasis stack on
# the example models (PiWind and others). It is co-located with the model data so a
# model/engine change and its worked example move together, and its own CI
# (model-tests.yml) can keep the examples honest.

project = "Oasis Models"
copyright = "Oasis Loss Modelling Framework"
author = "OasisLMF"

extensions = [
    "myst_nb",            # Markdown (MyST) + executable notebooks
    "sphinx_design",      # cards / grids
    "sphinx_copybutton",  # copy button on code blocks
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "myst-nb",
    ".ipynb": "myst-nb",
}

myst_enable_extensions = ["colon_fence", "deflist", "substitution", "tasklist"]
myst_heading_anchors = 3

# -- Executable notebooks (myst-nb) -----------------------------------------
# The worked examples SHOW the engine run as a command (`oasislmf model run ...`)
# but do NOT execute the engine at docs-build — the runnable cells only analyse the
# ORD outputs a run produces (cheap pandas/matplotlib on committed sample outputs).
# So the docs build never runs the model; a cell error still fails the build, so the
# analysis stays a smoke test. A notebook that genuinely runs the engine should set
# `nb_execution_mode: off` in its own front-matter and ship committed outputs.
nb_execution_mode = "cache"
nb_execution_raise_on_error = True
nb_execution_timeout = 120

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_title = "Oasis Models"


# -- Cross-component links (intersphinx, aggregated site) --------------------
# The GenerateDocs orchestrator sets OASIS_INTERSPHINX_MAP (JSON) to point cross-references at
# the other components' built inventories; standalone builds add nothing. Use explicit roles,
# e.g. {external+ord:doc}`reference/tables` or :external+oed:ref:`some-label`.
import json as _ix_json, os as _ix_os
if "sphinx.ext.intersphinx" not in extensions:
    extensions = list(extensions) + ["sphinx.ext.intersphinx"]
try:
    intersphinx_mapping
except NameError:
    intersphinx_mapping = {}
intersphinx_mapping.update({
    _k: (_v[0], _v[1])
    for _k, _v in _ix_json.loads(_ix_os.environ.get("OASIS_INTERSPHINX_MAP", "{}")).items()
})
