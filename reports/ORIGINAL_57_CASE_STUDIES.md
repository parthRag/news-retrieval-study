# Original benchmark: measured case studies

Cases are the two largest positive and two largest negative E5-minus-BM25 nDCG@5 differences. Grades come from the original qrels; **unjudged is not a verified grade 0**. Opening passages provide inspection evidence, not automatic rationales or explanations of neural reasoning.

## Query 870: Seven transgender women have been killed this year. Democrats want Jeff Sessions to investigate.

BM25 nDCG@5: **0.0000**; E5: **0.9294**; E5 minus BM25: **+0.9294**.

| Engine | Rank | Supplied grade | Article |
| --- | ---: | ---: | --- |
| BM25 | 1 | 0 | Hill Democrats slam Trump’s military transgender ban, while GOP is caught by surprise |
| BM25 | 2 | 0 | Democrats fear that Trump has barred key federal workers from speaking to them |
| BM25 | 3 | 0 | Trump administration rolls back protections for transgender students |
| BM25 | 4 | 0 | Sessions emphasizes the primacy of the law over his political views |
| BM25 | 5 | 0 | The nearly indestructible bond between Jeff Sessions and Donald Trump |
| E5 | 1 | 4 | Transgender killings on the rise: ‘This is just so crazy’ |
| E5 | 2 | 2 | Gang member who killed transgender woman he was dating is first to be sentenced under federal hate crime law |
| E5 | 3 | 1 | D.C. police probe recent attacks on gay, transgendered but say only one hate-related |
| E5 | 4 | 1 | Was the victim in brutal Fresno killing a transgender woman? ‘We may never know.’ |
| E5 | 5 | 1 | Violence lurks in the shadows for transgender sex workers |

**BM25 rank-one evidence** (`288bf3ae-7212-11e7-8f39-eeb7d3a2d304`):

> Lawmakers in both parties slammed President Trump’s decision on Wednesday to bar transgender Americans from serving in the military, while many of his allies on Capitol Hill remained largely perplexed or silent. The president’s decision, announced in a series of tweets, is yet another move that confused and divided elements of his party at a time when it is already roiled by disagreements over the future of a proposed health-care overhaul and of embattled Attorney General Jeff Sessions, who has faced a barrage of criticism from Trump in recent days. Rep. Thomas J. Rooney (R-Fla.), a former Army officer, said “it throws us off” when Trump issu


**E5 rank-one evidence** (`c1782bce9efda611752f3b58a546db92`):

> 2015 has been a year of milestones for transgender Americans, from the coming out of Caitlyn Jenner to the decision to allow trans men and women to openly serve in the military. *[WSU]: Wayne State University *[Tue]: Tuesday *[Wed]: Wednesday *[UNM]: University of New Mexico But underneath the banner year lies a dark truth: A higher profile for transgender Americans hasn’t translated into greater protection. In fact, just the opposite. According to transgender advocacy groups, at least 13 trans women have been killed so far this year. Eleven of the 13 victims have been women of color. And four of the deaths have come in just the last month. T

**Observed pattern and interpretation:** BM25's five leading results are all judged 0 and focus on politics, transgender policy or Sessions. Its leading article mentions Sessions and transgender military service while omitting killing-related language in the inspected body. E5 instead retrieves reporting about killings and violence, beginning with a grade-4 article that does not name Sessions. This is consistent with entity-focused lexical distraction versus retrieval of the central event, but does not prove an internal neural reasoning mechanism.

## Query 830: Scientists discover new frog species small enough to sit on a fingernail

BM25 nDCG@5: **0.1491**; E5: **0.8289**; E5 minus BM25: **+0.6798**.

| Engine | Rank | Supplied grade | Article |
| --- | ---: | ---: | --- |
| BM25 | 1 | 0 | Bat with record-breaking tongue found in the Bolivian jungle |
| BM25 | 2 | 0 | Scientists discover the first truly venomous frogs |
| BM25 | 3 | 1 | Scientists try to save the frogs as time runs out |
| BM25 | 4 | 0 | Smithsonian scientists discover gold bat along with four other new species |
| BM25 | 5 | 1 | New species of frog named after Ozzy Osbourne for its shrill call |
| E5 | 1 | 4 | Seven new species of miniature frogs discovered (and they’re adorable) |
| E5 | 2 | Unjudged | An ancient ‘misfit’ finally finds a family |
| E5 | 3 | 1 | This brand new species of tree frog is already in trouble |
| E5 | 4 | 1 | These frogs might be evolving right in front of us |
| E5 | 5 | 0 | Scientists discover the first truly venomous frogs |

**BM25 rank-one evidence** (`6d1bfb656d47d28880132cf14eff94a6`):

> The tube-lipped nectar bat isn't a new species -- it was discovered in 2005. But since its discovery in Ecuador, the bat -- which, with a tongue 150 percent the size of its body, breaks the record for the longest relative tongue on a mammal -- has only been found a handful of times. *[WSU]: Wayne State University *[Tue]: Tuesday *[Wed]: Wednesday *[UNM]: University of New Mexico [ _Hummingbird tongues are way weirder than we thought_ ] *[WSU]: Wayne State University *[Tue]: Tuesday *[Wed]: Wednesday *[UNM]: University of New Mexico And now the bat has been identified in a new location: Bolivia's Madidi National Park. The little guy with the b


**E5 rank-one evidence** (`2dbf3ec028fd1ba5f1946273d32a2c66`):

> Researchers have found seven new species of the miniature frog genus _Brachycephalus_ living on seven different mountains in the Atlantic Rainforest of Brazil. Living separately from each other and forced by several factors to keep to their own mountain tops, the members of this genus have evolved into many varied -- but hard to find -- species. Most members of the genus stay under one centimeter long. The new species are described in a paper published in PeerJ. *[WSU]: Wayne State University *[Tue]: Tuesday *[Wed]: Wednesday *[UNM]: University of New Mexico [ _Newly discovered frog gives birth to live tadpoles, a first_ ] *[WSU]: Wayne State

**Observed pattern and interpretation:** E5 connects the query's 'small enough to sit on a fingernail' description with a grade-4 article about 'miniature frogs'. BM25's leading bat-titled article also discusses frog discoveries extensively in its body, so the lexical result is not explained by the headline alone. The measured grades distinguish the background links; a plausible explanation is better matching of the size/species concept by E5. Exact query-token counts for full text and the E5 prefix are saved in the evidence JSON.

## Query 852: Why the FDA’s new e-cigarette regulations are a gift to Big Tobacco (and could actually harm public health)

BM25 nDCG@5: **0.5353**; E5: **0.0457**; E5 minus BM25: **-0.4896**.

| Engine | Rank | Supplied grade | Article |
| --- | ---: | ---: | --- |
| BM25 | 1 | 0 | The FDA finally steps up on e-cigarettes |
| BM25 | 2 | 3 | FDA outlines plan to regulate e-cigarettes |
| BM25 | 3 | 2 | E-cigarette use triples among middle and high school students, study says |
| BM25 | 4 | 2 | High school, middle school kids now use more e-cigs than tobacco: CDC |
| BM25 | 5 | 2 | Teen vaping soars |
| E5 | 1 | 0 | The FDA’s new plans could just switch one form of nicotine addiction with another |
| E5 | 2 | Unjudged | The FDA didn’t go far enough in regulating e-cigarettes |
| E5 | 3 | Unjudged | The FDA just unveiled one of the most important public-health initiatives of the century |
| E5 | 4 | Unjudged | The FDA begins evaluating the risks and benefits offered by cigarette alternatives |
| E5 | 5 | 1 | Big Tobacco is cool with scary e-cigarette warnings because no one reads them anyway |

**BM25 rank-one evidence** (`90636012-1308-11e6-93ae-50921721165d`):

> OVER THE past several years, the e-cigarette business has boomed, tying public-health experts in knots. On one hand, the devices are far less dangerous than conventional cigarettes. It would be a public-health victory if every smoker stopped lighting up and chose to vape instead. On the other hand, e-cigarettes seem designed to appeal to children and teenagers. E-cigarette liquids come in a variety of candylike flavors that, according to federal health officials, have driven interest among young users. Some young people — it is unclear how many — would not have gotten hooked on nicotine without e-cigarettes. As youth e-cigarette use jumped — 


**E5 rank-one evidence** (`b918922e-7bb8-11e7-b2b1-aeba62854dfa`):

> As a physician who treats patients devastated by tobacco-caused lung disease, I was concerned by the Aug. 5 editorial “Breaking nicotine’s grip,” which embraced Food and Drug Administration Commissioner Scott Gottlieb’s plan for regulating tobacco products. The commissioner seems unconcerned about switching one form of nicotine addiction with another. Nicotine in any form is bad for your health, adversely affecting neurological and cardiovascular systems and reproductive health. Evidence shows that nicotine can be a gateway drug. Flavoring agents and other chemicals in e-cigarettes, when vaporized, are harmful. Mr. Gottlieb appears willing to

**Observed pattern and interpretation:** BM25 receives its advantage from grades 3/2/2/2 at ranks 2–5, while both systems' rank-one articles are judged 0. Three of E5's top-five articles are unjudged and contribute zero under the declared convention. Its top article discusses a different FDA nicotine plan. This example mixes a measured focus mismatch with incomplete judgment coverage; the unjudged articles cannot be called confirmed semantic failures. The three grade-2 BM25 articles also have very similar opening text; near-duplicate suppression was not applied, so this result does not establish an advantage in information diversity.

## Query 827: House panel probes drug distributors and DEA amid national opioid crisis

BM25 nDCG@5: **0.5703**; E5: **0.2312**; E5 minus BM25: **-0.3391**.

| Engine | Rank | Supplied grade | Article |
| --- | ---: | ---: | --- |
| BM25 | 1 | 2 | Investigation: The DEA slowed enforcement while the opioid epidemic grew out of control |
| BM25 | 2 | 1 | U.S. senator calls for investigation of DEA enforcement slowdown amid opioid crisis |
| BM25 | 3 | 2 | How drugs intended for patients ended up in the hands of illegal users: ‘No one was doing their job’ |
| BM25 | 4 | 2 | This company’s drugs helped fuel Florida’s opioid crisis. But the government struggled to hold it accountable. |
| BM25 | 5 | 4 | Opioid distributors sued by West Virginia counties hit by drug crisis |
| E5 | 1 | Unjudged | Locating blame in the opioid epidemic |
| E5 | 2 | 1 | U.S. senator calls for investigation of DEA enforcement slowdown amid opioid crisis |
| E5 | 3 | 2 | Drugmakers and distributors face barrage of lawsuits over opioid epidemic |
| E5 | 4 | 1 | Drug industry hired dozens of officials from the DEA as the agency tried to curb opioid abuse |
| E5 | 5 | 1 | Senate panel investigates drug companies’ ties to pain groups |

**BM25 rank-one evidence** (`aea2bf8e-7f71-11e6-8d13-d7c704ef9fd9`):

> **UNNATURAL CAUSES** SICK AND DYING IN SMALL-TOWN AMERICA: _Since the turn of this century, rates have risen for whites in midlife, particularly women.In this series, The Washington Post is exploring this trend and the forces driving it. Related: Wholesalers sent pills to drugstores that fueled the opioid epidemic _ A decade ago, the Drug ­Enforcement Administration launched an aggressive campaign to curb a rising opioid epidemic that was claiming thousands of American lives each year. The DEA began to target wholesale companies that distributed hundreds of millions of highly addictive pills to the corrupt pharmacies and pill mills that illeg


**E5 rank-one evidence** (`2fd5dc30-9c78-11e6-b3c9-f662adaa0048`):

> DESTRUCTIVE AND persistent, the epidemic of opioid addiction is also deeply ironic: Unlike previous drug scourges in U.S. history, this one spread via perfectly legal channels. Millions of people were introduced to addictive pain-killing medications by doctors’ prescriptions, filled at pharmacies, ultimately supplied by pharmaceutical manufacturers. All of this went on in one of the most heavily regulated sectors of the U.S. economy — health care — which is supervised by a veritable army of officials working for dozens of agencies, state and federal. Understandably, Americans want to know how the corporate, governmental and medical establishm

**Observed pattern and interpretation:** All five BM25 results are positively judged, including a grade-4 document at rank five; E5 has an unjudged rank-one article and lower-graded positive links. The BM25 lead is a 30,729-character investigation of DEA enforcement and distributors, while E5's lead is a shorter editorial using the alternate term 'wholesalers'. Both are topically connected, so lexical specificity, article coverage and incomplete judgments are competing explanations. This result does not establish that E5 failed to understand the opioid topic.

## Interpretation limits

These headline/background-linking results support a diagnosis of topic focus and judgment coverage. They do not test whether either system obeys the 20 custom negation, homonym or temporal constraints. Article-level excerpts cannot establish why E5 assigned a score. Full-body versus 512-token input coverage and incomplete judgments remain competing explanations.
