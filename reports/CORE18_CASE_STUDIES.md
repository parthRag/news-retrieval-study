# Core 2018 paired ranking examples


These are the two extremes of E5-minus-BM25 rewrite-change advantage, selected after scoring. They illustrate variability and are not a representative sample. Grades below are supplied NIST judgments, not new assessments; an unjudged hit remains explicitly unjudged. New rewrite intent still needs independent human review.


## Topic 814: China one-child impact


Original: **China one-child impact**. Rewrite: **consequences of China's single-child rule**. Differential change: **-0.5760 nDCG@5**.


Official narrative: Relevant documents will contain discussion of the impact China's one-child policy has had on its economy and/or social structure.


| Formulation | Engine | nDCG@5 |
| --- | --- | --- |
| title | bm25 | 0.4240 |
| title | dense | 1.0000 |
| rewrite | bm25 | 1.0000 |
| rewrite | dense | 1.0000 |


| Formulation | Engine | Rank | NIST grade | Article title | ID |
| --- | --- | --- | --- | --- | --- |
| title | bm25 | 1 | 2 | China should abolish its one-child policy altogether | `f52d203c-51f4-11e3-9e2c-e1d01116fd98` |
| title | bm25 | 2 | 0 | State Department reprimands China over sex trafficking and forced labor | `c55cc80b-3b3d-49f7-827a-52416946c394` |
| title | bm25 | 3 | 1 | Biden to attempt damage control in visit with Chinese leader | `48d8845c-56b3-11e3-8304-caf30787c0a9` |
| title | dense | 1 | 2 | China should abolish its one-child policy altogether | `f52d203c-51f4-11e3-9e2c-e1d01116fd98` |
| title | dense | 2 | 2 | China’s lifting of its one-child policy can’t undo the damage already done | `6c885b64-7f3f-11e5-b575-d8dcfedb4ea1` |
| title | dense | 3 | 2 | A taboo left unexplored in ‘one-child’ policy reporting | `582c4702-8183-11e5-8bd2-680fff868306` |
| rewrite | bm25 | 1 | 2 | The loneliness of China’s one-child rule | `f283a330-0292-11e3-bfc5-406b928603b2` |
| rewrite | bm25 | 2 | 2 | ‘One is enough’: Chinese families lukewarm over easing of one-child policy | `bdfeff1e-9d7e-11e4-86a3-1b56f64925f6` |
| rewrite | bm25 | 3 | 2 | The human suffering caused by China’s one-child policy | `998c085d46b4af60be956d9f75ef5859` |
| rewrite | dense | 1 | 2 | The loneliness of China’s one-child rule | `f283a330-0292-11e3-bfc5-406b928603b2` |
| rewrite | dense | 2 | 2 | China should abolish its one-child policy altogether | `f52d203c-51f4-11e3-9e2c-e1d01116fd98` |
| rewrite | dense | 3 | 2 | Six questions on China’s one-child policy, answered | `ad64af1c-4def-11e3-be6b-d3d28122e6d4` |


The table establishes changes in observed ranking and reference grades. It does not establish a causal account of model reasoning; inspect the article text and retained E5 prefix in the demo.


E5 stays at 1.0000 in both formulations. Its negative differential advantage comes from BM25 improving, rather than from E5 failing. Absolute quality and robustness change are different quantities.


## Topic 825: ethanol and food prices


Original: **ethanol and food prices**. Rewrite: **maize alcohol fuel and food costs**. Differential change: **+0.9462 nDCG@5**.


Official narrative: Identify documents that discuss the impact of growing corn with the intention of using it for ethanol fuel on food prices in the U.S.


| Formulation | Engine | nDCG@5 |
| --- | --- | --- |
| title | bm25 | 0.8422 |
| title | dense | 0.4704 |
| rewrite | bm25 | 0.0000 |
| rewrite | dense | 0.5743 |


| Formulation | Engine | Rank | NIST grade | Article title | ID |
| --- | --- | --- | --- | --- | --- |
| title | bm25 | 1 | 2 | Study: U.S. could put a big dent in corn prices by relaxing ethanol rules | `2e0c4ffa3fb7089f43965bef7ee6d4d2` |
| title | bm25 | 2 | 2 | Amid a devastating drought, does it still make sense to use corn for fuel? | `d9cbfdd3a4593477feee99eb4f3a28be` |
| title | bm25 | 3 | 1 | Mr. Cruz is right about ending the ethanol mandate | `29fc87b8-b656-11e5-a76a-0b5145e8679a` |
| title | dense | 1 | 2 | Study: U.S. could put a big dent in corn prices by relaxing ethanol rules | `2e0c4ffa3fb7089f43965bef7ee6d4d2` |
| title | dense | 2 | 0 | Charles Lane: Ethanol mandates creating an economic pileup | `17346b08-08ef-11e3-8974-f97ab3b3c677` |
| title | dense | 3 | 0 | Ethanol takes policy blow from the Environmental Protection Agency | `79fb5268-4e33-11e3-be6b-d3d28122e6d4` |
| rewrite | bm25 | 1 | Unjudged | Study: Global crop production shows some signs of stagnating | `17058cd4ab0b3964b4174fcea0c8b338` |
| rewrite | bm25 | 2 | 0 | Think you know corn? Chew on this. | `5dfcfec2-25af-11e5-b77f-eb13a215f593` |
| rewrite | bm25 | 3 | Unjudged | Mummies reveal coca, alcohol use in Incan ritual sacrifices | `74660e7e-fb86-11e2-8752-b41d7ed1f685` |
| rewrite | dense | 1 | 2 | Study: U.S. could put a big dent in corn prices by relaxing ethanol rules | `2e0c4ffa3fb7089f43965bef7ee6d4d2` |
| rewrite | dense | 2 | 0 | Ethanol takes policy blow from the Environmental Protection Agency | `79fb5268-4e33-11e3-be6b-d3d28122e6d4` |
| rewrite | dense | 3 | 2 | Congress’s wrongheaded approach to drought relief | `16211a12-dcc8-11e1-9974-5c975ae4810f` |


The table establishes changes in observed ranking and reference grades. It does not establish a causal account of model reasoning; inspect the article text and retained E5 prefix in the demo.


BM25 loses its known-positive top-five results after the rewrite, while E5 keeps the same grade-2 lead article. Some BM25 rewrite hits are unjudged, so a zero reference score does not establish that all retrieved articles are irrelevant.

