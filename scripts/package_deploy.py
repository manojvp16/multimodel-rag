"""Export deployment source without credentials, user PDFs, or nested Git data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    'Dockerfile', '.dockerignore', '.gitignore', '.env.deploy.example',
    'render.yaml', 'compose.deploy.yaml', 'docker-compose.yml', 'README.md', 'DEPLOYMENT.md',
    'backend/pyproject.toml', 'backend/uv.lock', 'backend/README.md',
    'backend/.env.example', 'backend/.gitignore', 'backend/.python-version',
    'frontend/package.json', 'frontend/package-lock.json', 'frontend/index.html',
    'frontend/style.css', 'frontend/vite.config.js', 'frontend/README.md', 'frontend/.gitignore',
)
SOURCE_TREES = (
    ('backend/src', {'.py'}), ('backend/tests', {'.py'}), ('backend/docs', {'.md'}),
    ('frontend/src', {'.js', '.jsx', '.css'}), ('frontend/tests', {'.js'}), ('scripts', {'.py'}),
)


def source_files():
    files = {ROOT / name for name in ROOT_FILES}
    for directory, extensions in SOURCE_TREES:
        files.update(path for path in (ROOT / directory).rglob('*') if path.is_file() and path.suffix in extensions)
    for path in sorted(files):
        if not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f'Missing or invalid deployment source: {path.relative_to(ROOT)}')
        yield path


def main():
    output = ROOT / 'dist' / 'omnirag-deploy.zip'
    files = list(source_files())
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f'Created {output} ({len(files)} source files; no uploaded documents or private environment files).')


if __name__ == '__main__':
    main()
