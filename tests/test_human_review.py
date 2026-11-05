from collections import Counter

import pytest

from news_ir.human_review import select_article_pairs, validate_return, review_views


def article(task_id='J001'):
    return {'task_id':task_id, 'kind':'relevance', 'priority':'required',
            'query_id':'N01', 'doc_id':'doc1', 'article_contents':'Study found no decline in employment.',
            'contents_sha256':'fixture'}


def test_sample_counterbalances_without_relevance_labels_and_uses_distinct_docs():
    queries = [{'_id':f'{kind}{i}', 'category':kind} for kind in ['V','N','H','T'] for i in range(10)]
    runs = {engine:{q['_id']:['a','b','c','d','e'] for q in queries} for engine in ['bm25','dense']}
    selected = select_article_pairs(queries, runs)
    assert selected == select_article_pairs(queries, runs)
    assert len(selected) == 80
    for q in queries:
        rows = [r for r in selected if r['query_id'] == q['_id']]
        assert len({r['doc_id'] for r in rows}) == 2
        assert {r['target_engine'] for r in rows} == {'bm25','dense'}
    for category in ['V','N','H','T']:
        counts = Counter(r['target_engine'] for r in selected if r['wave']==1 and r['query_id'].startswith(category))
        assert counts == {'bm25':5, 'dense':5}


def test_blank_and_uncertain_rows_cannot_become_complete_human_labels():
    tasks = [article(), article('J002')]
    report = validate_return(tasks, [{'task_id':'J001','reviewer':'Human','grade':''},
                                     {'task_id':'J002','reviewer':'Human','grade':'U','reason':'Cannot determine the event date.'}])
    assert report['required_resolved'] == 0
    assert report['uncertain_rows'] == 1 and report['blank_rows'] == 1
    assert report['actual_reviewer_count'] == 1


def test_grade_requires_full_read_and_provided_evidence_must_be_exact():
    row = {'task_id':'J001','reviewer':'Human','grade':2,'reason':'Provides the requested negative finding.',
           'full_article_read':True,'evidence_quote':'no decline in employment'}
    report = validate_return([article()], [row])
    assert report['required_resolved'] == 1
    assert report['accepted'][0]['evidence'][0]['start'] == 12
    with pytest.raises(ValueError, match='literal'):
        validate_return([article()], [{**row,'evidence_quote':'made up quote'}])
    with pytest.raises(ValueError, match='full available'):
        validate_return([article()], [{**row,'full_article_read':False}])
    with pytest.raises(ValueError, match='0, 1, 2'):
        validate_return([article()], [{**row,'grade':True}])
    with pytest.raises(ValueError, match='0, 1, 2'):
        validate_return([article()], [{**row,'grade':1.0}])
    without_notes = {k:v for k,v in row.items() if k not in {'reason','evidence_quote'}}
    report = validate_return([article()], [without_notes])
    assert report['required_resolved'] == 1
    assert 'evidence' not in report['accepted'][0]


def test_zero_and_uncertain_grades_accept_labels_without_written_justifications():
    report = validate_return([article()], [{'task_id':'J001','reviewer':'Human','grade':0,
        'full_article_read':True}])
    assert report['required_resolved'] == 1
    report = validate_return([article()], [{'task_id':'J001','reviewer':'Human','grade':'U'}])
    assert report['uncertain_rows'] == 1 and report['required_resolved'] == 0


def test_rewrite_verdicts_and_reviewer_identity_are_separate_from_relevance():
    task = {'task_id':'R001','kind':'rewrite','priority':'required','topic_id':'1','dataset':'fixture'}
    row = {'task_id':'R001','reviewer':'Parth','verdict':'narrower'}
    report = validate_return([task],[row])
    assert report['required_resolved'] == 1
    assert report['accepted'][0]['topic_id'] == '1'
    with pytest.raises(ValueError,match='duplicate reviewer'):
        validate_return([task],[row,row])
    with pytest.raises(ValueError,match='reviewer name'):
        validate_return([task],[{**row,'reviewer':''}])


def test_time_and_team_views_preserve_task_identity_and_coverage():
    tasks = [{'task_id':f'R{i}', 'kind':'rewrite','priority':'required','batch':'ABCD'[i%4]} for i in range(54)]
    tasks += [{'task_id':f'J{i}', 'kind':'relevance','priority':'required','batch':'ABCD'[i%4], 'category':str(i//10)} for i in range(40)]
    tasks += [{'task_id':f'X{i}', 'kind':'relevance','priority':'optional','batch':'ABCD'[i%4]} for i in range(40)]
    views = {name:rows for name,_,rows in review_views(tasks)}
    assert len(views['TIME_LIMITED.html']) == 66
    assert len(views['SECOND_REVIEWER_8.html']) == 8
    first = {t['task_id'] for t in views['TWO_REVIEWERS_1.html']}
    second = {t['task_id'] for t in views['TWO_REVIEWERS_2.html']}
    assert not first & second
    assert first | second == {t['task_id'] for t in views['START_HERE.html']}
