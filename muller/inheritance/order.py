from typing import Dict, List, Tuple

import pandas
from loguru import logger

try:
	from muller.inheritance import scoring
	from muller.inheritance.cluster import Cluster
except ModuleNotFoundError:
	from . import scoring
	from .cluster import Cluster


def order_clusters(sorted_df: pandas.DataFrame, dlimit: float, additive_cutoff: float, derivative_cutoff: float,
		known_ancestry: Dict[str, str] = None) -> Cluster:
	"""
		Orders genotypes by which background they belong to.
	Parameters
	----------
	sorted_df: pandas.DataFrame
		A dataframe of sorted genotypes based on when the genotype was first detected and first fixed.
	dlimit: float
		The detection limit
	additive_cutoff: float
		Used when testing whther a nested genotype is consistently greater than an unnested genotype
	derivative_cutoff: float
		Used when testing whether two genotypes are correlated, not correlated, or anticorrelated. correlated/anticorrelated genotypes
		must have a covariance outside the range [-`derivative_cutoff`, `derivative_cutoff`].
	known_ancestry: Dict[str,str]
		Manually-assigned ancestry values. For now, the parent genotype is automatically assigned to the root genotype to prevent
		circular links from forming.

	Returns
	-------
	ClusterType
	"""
	# By default the backgrounds should occupy the first n lines of the dataframe
	if known_ancestry is None: known_ancestry = dict()

	initial_background = sorted_df.iloc[0]
	genotype_nests = Cluster(initial_background, timepoints = sorted_df)
	if known_ancestry:
		logger.info(f"Found user-given ancestries.")
	for identity, parent in known_ancestry.items():
		# TODO need to add a way to prevent circular ancestry links when a user manually assigns ancestry. Current workaround forces the manual parent to be in the root background.
		# TODO Also need to add a way to specify a genotype by one of the linked annotations.
		logger.info(f"Adding {parent} as a potential background for {identity}")
		genotype_nests.add_genotype_to_background(parent, 'genotype-0', priority = 100)
		genotype_nests.add_genotype_to_background(identity, parent, priority = 100)  # Dummy priority so that it is selected before other backgrounds.
	for unnested_label, unnested_trajectory in sorted_df[1:].iterrows():
		logger.debug(f"Nesting {unnested_label}")
		# Iterate over the rest of the table in reverse order. Basically, we start with the newest nest and iterate until we find a nest that satisfies the filters.
		test_table = sorted_df[:unnested_label].iloc[::-1]
		for nested_label, nested_genotype in test_table.iterrows():
			if nested_label == unnested_label: continue
			score_additive = scoring.calculate_additive_score(nested_genotype, unnested_trajectory, additive_cutoff)
			score_derivative = scoring.calculate_derivative_score(nested_genotype, unnested_trajectory, detection_cutoff = dlimit,
				cutoff = derivative_cutoff)
			score_area = scoring.calculate_area_score(nested_genotype, unnested_trajectory)

			total_score = score_additive + score_derivative + score_area
			logger.debug(f"{unnested_label}\t{nested_label}\t{total_score}")
			genotype_nests.add_genotype_to_background(unnested_label, nested_label, total_score)
	logger.debug("Final Ancestry:")
	for genotype_label in sorted_df.index:
		candidate = genotype_nests.get_highest_priority(genotype_label)
		logger.debug(f"{genotype_label}\t{candidate}")
	return genotype_nests


def get_maximum_genotype_delta(genotype_deltas: List[Tuple[str, float]]) -> Tuple[str, float]:
	if genotype_deltas:
		correlated_label, correlated_delta = max(genotype_deltas, key = lambda s: s[1])
	else:
		correlated_label = "N/A"  # Shouldn't end up being used.
		correlated_delta = 0
	return correlated_label, correlated_delta


if __name__ == "__main__":
	pass
