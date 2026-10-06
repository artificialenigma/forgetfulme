"""Run one local cited answer using already compiled sources; keep output private."""
import uuid
from pathlib import Path
from app.db import connect
from app.wiki import answer_one, WIKI

identifier=uuid.uuid4()
try:
    with connect() as db:
        row=db.execute("SELECT wiki_data FROM page_captures WHERE ai_state='complete' AND jsonb_array_length(wiki_data->'concepts')>0 LIMIT 1").fetchone()
        assert row, 'Waiting for a compiled source with grounded concepts'
        concept=row['wiki_data']['concepts'][0]['name']
        db.execute('INSERT INTO wiki_questions(id,question) VALUES (%s,%s)',(identifier,'What do the sources say about '+concept+'?'))
    answer_one()
    with connect() as db:
        result=db.execute('SELECT state,citations FROM wiki_questions WHERE id=%s',(identifier,)).fetchone()
        assert result['state']=='complete', 'Local question processing did not complete'
        assert result['citations'], 'Answer has no citations'
    assert (Path('/vault')/WIKI/'queries'/f'{identifier}.md').is_file()
    print('Live local question answered, source citations validated, answer saved to vault')
finally:
    with connect() as db: db.execute('DELETE FROM wiki_questions WHERE id=%s',(identifier,))
    (Path('/vault')/WIKI/'queries'/f'{identifier}.md').unlink(missing_ok=True)
