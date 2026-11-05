"""Check returned JSON/CSV responses without publishing or changing any scores."""
import argparse
import csv
import io
import json
from pathlib import Path

from news_ir.data import sha256_file
from news_ir.human_review import digest, validate_return

ROOT = Path(__file__).resolve().parents[1]


def read_responses(path, payload):
    if path.suffix.lower() == '.json':
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get('schema') != payload['schema'] or data.get('pack_id') != payload['pack_id']
                or data.get('tasks_sha256') != payload['tasks_sha256']):
            raise ValueError('Response file belongs to another review pack')
        if not isinstance(data.get('reviews'), list):
            raise ValueError('JSON response needs a reviews list')
        for row in data['reviews']:
            if row.get('reviewer') and row['reviewer'] != data.get('reviewer'):
                raise ValueError('JSON header and row reviewer identities differ')
        return data['reviews']
    if path.suffix.lower() != '.csv':
        raise ValueError('Use exported JSON or a completed CSV')
    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        text = path.read_text(encoding='cp1252')
    tasks = {t['task_id']: t for t in payload['tasks']}
    result = []
    for row in csv.DictReader(io.StringIO(text)):
        task = tasks.get(row.get('task_id'))
        if task is None:
            raise ValueError('Unknown CSV task ID')
        for key in ['doc_id', 'query_id', 'topic_id', 'original', 'rewrite']:
            if key in row and row[key] and row[key] != str(task.get(key, '')):
                raise ValueError(f"{task['task_id']}: source metadata changed in CSV ({key})")
        row = {k: (v or '').strip() for k, v in row.items()}
        row['verdict'] = row.get('verdict', '').lower()
        raw = row.get('grade', '')
        if raw in {'0', '1', '2'}:
            row['grade'] = int(raw)
        elif raw.upper() == 'U':
            row['grade'] = 'U'
        elif raw:
            raise ValueError(f"{task['task_id']}: grade must be 0, 1, 2 or U")
        read = row.get('full_article_read', '').lower()
        if read not in {'', 'yes', 'true', '1', 'no', 'false', '0'}:
            raise ValueError('full_article_read must be yes/no or true/false')
        row['full_article_read'] = read in {'yes', 'true', '1'}
        quote = row.get('evidence_quote', '')
        if task['kind'] == 'relevance' and quote.startswith(("'=", "'+", "'-", "'@")):
            if quote[1:] in task['article_contents']:
                row['evidence_quote'] = quote[1:]
        result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, default=ROOT/'artifacts/assessments/human-review-round1')
    parser.add_argument('--reviews', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, help='New JSON destination for validated rows; existing files refused')
    args = parser.parse_args()
    payload = json.loads((args.pack/'tasks.json').read_text(encoding="utf-8"))
    if digest(payload['tasks']) != payload['tasks_sha256']:
        raise ValueError('Frozen review task data changed')
    manifest = json.loads((args.pack/'manifest.json').read_text(encoding="utf-8"))
    for name, expected in manifest['files'].items():
        # The worksheet CSVs are explicitly editable response files. Immutable
        # JSON/HTML/instructions remain bound; CSV identity is checked per row.
        if Path(name).suffix != '.csv' and sha256_file(args.pack/name) != expected:
            raise ValueError('Immutable review packet file changed: ' + name)
    reviews = []
    for path in args.reviews:
        reviews.extend(read_responses(path, payload))
    result = validate_return(payload['tasks'], reviews)
    if args.output:
        if args.output.exists():
            raise FileExistsError('Preserve prior human review exports; choose a new output')
        args.output.parent.mkdir(exist_ok=True, parents=True)
        args.output.write_text(json.dumps({'pack_id':payload['pack_id'], **result}, indent=2)+'\n', encoding="utf-8", newline="\n")
    print(json.dumps({k:v for k,v in result.items() if k not in {'accepted','uncertain'}}, indent=2))


if __name__ == '__main__':
    main()
