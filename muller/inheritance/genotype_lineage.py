from typing import Dict, List, Optional, Tuple

import pandas
from loguru import logger

try:
	from muller.inheritance import scoring
	from muller.inheritance.genotype_ancestry import Ancestry
	from muller import widgets
except ModuleNotFoundError:
	from . import scoring
	from .genotype_ancestry import Ancestry
	from .. import widgets


class LineageWorkflow:
	"""
		Orders genotypes by which background they belong to.
	Parameters
	----------
	dlimit: float
		The detection limit
	flimit: float
		The cutoff value to consider a genotype "fixed"
	pvalue: float
		The pvalue to use for statistical tests.
	"""

	def __init__(self, dlimit: float, flimit: float, pvalue:float, debug:bool = False):
		self.dlimit = dlimit
		self.flimit = flimit
		self.pvalue = pvalue
		self.debug = debug
		self.genotype_nests: Optional[Ancestry] = None

		self.scorer = scoring.Score(self.dlimit, self.flimit, self.pvalue)
		self.score_records:List[Dict[str,float]] = list() # Keeps track of the individual score values for each pair
	def __repr__(self):
		return f"LineageWorkflow(dlimit = {self.dlimit}, flimit = {self.flimit}, pvalue = {self.pvalue})"
	def add_known_lineages(self, known_ancestry: Dict[str, str]):
		for identity, parent in known_ancestry.items():
			# TODO need to add a way to prevent circular ancestry links when a user manually assigns ancestry. Current workaround forces the manual parent to be in the root background.
			logger.debug(f"Adding {parent} as a potential background for {identity}")
			self.genotype_nests.add_genotype_to_background(parent, 'genotype-0', priority = 100)
			# Use a dummy priority so that it is selected before other backgrounds.
			self.genotype_nests.add_genotype_to_background(identity, parent, priority = 100)



	def show_ancestry(self, sorted_genotypes: pandas.DataFrame):
		logger.log("COMPLETE", "Final Ancestry:")
		for genotype_label in sorted_genotypes.index:
			candidate = self.genotype_nests.get_highest_priority(genotype_label)
			logger.log('COMPLETE', f"{genotype_label}\t{candidate}")

	def run(self, sorted_genotypes: pandas.DataFrame, known_ancestry: Dict[str, str] = None) -> Ancestry:
		"""
			Infers the lineage from the given genotype table.
		Parameters
		----------
		sorted_genotypes: pandas.DataFrame
			A dataframe of sorted genotypes based on when the genotype was first detected and first fixed.
		known_ancestry: Dict[str,str]
			Manually-assigned ancestry values. For now, the parent genotype is automatically assigned to the root genotype to prevent
			circular links from forming.
		"""

		initial_background = sorted_genotypes.iloc[0]
		self.genotype_nests = Ancestry(initial_background, timepoints = sorted_genotypes)
		self.add_known_lineages(known_ancestry if known_ancestry else dict())

		for unnested_label, unnested_trajectory in sorted_genotypes[1:].iterrows():
			# Iterate over the rest of the table in reverse order. Basically, we start with the newest nest and iterate until we find a nest that satisfies the filters.
			test_table = sorted_genotypes[:unnested_label].iloc[::-1]
			for nested_label, nested_genotype in test_table.iterrows():
				if nested_label == unnested_label: continue
				score_data = self.scorer.score_pair(nested_genotype, unnested_trajectory)
				self.score_records.append(score_data)
				self.genotype_nests.add_genotype_to_background(unnested_label, nested_label, score_data['totalScore'])

		self.show_ancestry(sorted_genotypes)
		if self.debug:
			df = pandas.DataFrame(self.score_records)
			#df.to_csv("strongselection.tsv", sep = '\t')
			logger.debug(df.to_string())

		return self.genotype_nests


def get_maximum_genotype_delta(genotype_deltas: List[Tuple[str, float]]) -> Tuple[str, float]:
	if genotype_deltas:
		correlated_label, correlated_delta = max(genotype_deltas, key = lambda s: s[1])
	else:
		correlated_label = "N/A"  # Shouldn't end up being used.
		correlated_delta = 0
	return correlated_label, correlated_delta


if __name__ == "__main__":
	filename = "/home/cld100/Documents/github/muller_diagrams/tests/data/tables/generic.genotypes.5.xlsx"
	table = pandas.read_excel(filename, sheet_name = "sorted").set_index('Genotype')

	lineage = LineageWorkflow(0.03, 0.97, 0.05)

	result = lineage.run(table)
	from pprint import pprint
	records = lineage.score_records
	print(pandas.DataFrame(records).to_string())