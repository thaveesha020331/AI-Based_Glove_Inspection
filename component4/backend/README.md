# GloveIQ Flask API

The backend uses an application factory, SQLAlchemy models, Flask-Migrate, and
blueprints. It is intentionally independent of upstream computer-vision and sorting
components: standardized inspection records can be imported through the data-management
API in a later slice.

Python 3.15 is supported. The analytics dependencies use compatible release ranges
because older pinned Pandas/NumPy/scikit-learn releases do not provide Python 3.15
wheels and would attempt a local C/C++ build on Windows.

Run with `python -m pip install -r requirements.txt` and
`python -m flask --app run.py run --debug`.
