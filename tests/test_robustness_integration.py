import math

import numpy as np
import pytest

from news_ir.paired_stats import compare, holm
from news_ir.robustness import evaluate_extended, paired_formulation_tests, topic_cluster_feature_tests


def test_incomplete_judgments_and_missing_positive():
 pytest.importorskip('ir_measures')
 result=evaluate_extended({'1':['unjudged','good','bad']},{'1':{'good':2,'bad':0,'missing':1}})
 row=result['per_query']['1']
 assert row['ndcg_at_5']==pytest.approx((2/math.log2(3))/(2+1/math.log2(3)))
 assert row['condensed_ndcg_at_5']==pytest.approx(2/(2+1/math.log2(3)))
 assert row['ap_at_1000']==pytest.approx(.25)
 assert row['recall_at_100']==.5
 assert row['bpref']==.5
 assert row['judged_at_5']==pytest.approx(2/3)


def test_paired_changes_are_paired_by_topic_not_row_order():
 def evaluation(variant,values):
  return {'per_query':{f'{q}-{variant}':{m:v for m in ['ndcg_at_5','ndcg_at_10','ap_at_1000','condensed_ndcg_at_10','bpref']} for q,v in values}}
 variants={
  'title':{'bm25':evaluation('title',[('1',.8),('2',.6)]),'dense':evaluation('title',[('1',.7),('2',.6)])},
  'rewrite':{'bm25':evaluation('rewrite',[('2',.1),('1',.3)]),'dense':evaluation('rewrite',[('2',.5),('1',.6)])}}
 checks=paired_formulation_tests(variants,alternatives=('rewrite',))['ndcg_at_5']
 change=checks[-1]
 assert change['mean_diff']==pytest.approx(.4)
 assert change['n_topics']==2
 variants['rewrite']['dense']['per_query'].pop('1-rewrite')
 with pytest.raises(ValueError,match='identical topics'):paired_formulation_tests(variants,alternatives=('rewrite',))


def test_topic_aggregation_prevents_duplicate_rewrites_inflating_sample():
 rows=[{'topic_id':str(i),'advantage':float(i),'overlap':float(i)} for i in range(12) for _ in range(2)]
 result=topic_cluster_feature_tests(rows,['overlap'],samples=100)
 assert result['results'][0]['topics']==12
 assert result['results'][0]['spearman_rho']==pytest.approx(1)
 assert result['results'][0]['p_holm']<.05


def test_holm_and_topic_pair_identity():
 assert holm([.01,.02,.8])==pytest.approx([.03,.04,.8])
 with pytest.raises(ValueError,match='different topics'):
  compare({'a':{'1':{'metric':1}},'b':{'2':{'metric':1}}},[('a','b')],'metric')
