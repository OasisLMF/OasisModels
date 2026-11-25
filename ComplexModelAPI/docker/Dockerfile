# ComplexModelAPI model worker: the stock worker image plus this model's
# complex_model_wrapper package, which provides the custom gulcalc console script
# `ComplexAPIModelExample_gulcalc` called by src/model_execution_worker/supplier_model_runner.py
#
# Built by docker/worker-container.yml (context: the ComplexModelAPI directory).
# WORKER_IMG is the base worker image, so the platform version follows --worker-image / WORKER_IMG.
#
# setup.py imports complex_model_wrapper and oasislmf at build time, so the package is
# installed without build isolation (uses the image's own setuptools and oasislmf).
ARG WORKER_IMG=coreoasis/model_worker:latest
FROM ${WORKER_IMG}

COPY --chown=worker setup.py /tmp/pkg/
COPY --chown=worker complex_model_wrapper /tmp/pkg/complex_model_wrapper
RUN cd /tmp/pkg \
    && pip install --user --no-cache-dir --no-warn-script-location --no-build-isolation . \
    && rm -rf /tmp/pkg
