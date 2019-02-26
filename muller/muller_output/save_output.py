import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas
from dataclasses import dataclass
import itertools
# logging.basicConfig(level = logging.INFO, format = '%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)
ROOT_GENOTYPE_LABEL = "genotype-0"
FILTERED_GENOTYPE_LABEL = "removed"
OutputType = Tuple[pandas.DataFrame, pandas.DataFrame, str, Dict[str, Any]]

try:
	from muller.clustering.generate import GenotypeOptions
	from clustering.metrics.pairwise_calculation_cache import PairwiseCalculationCache
	from inheritance.sort_genotypes import SortOptions
	from inheritance.order import OrderClusterParameters
	from graphics import plot_genotypes, plot_heatmap, plot_dendrogram, generate_muller_plot
	from muller.muller_output.generate_tables import *
	from muller.muller_output.generate_scripts import generate_mermaid_script, generate_r_script, excecute_mermaid_script, execute_r_script
	from muller import widgets
	from muller.palette import generate_clade_palette
except ModuleNotFoundError:
	from clustering.metrics.pairwise_calculation_cache import PairwiseCalculationCache
	from graphics import plot_genotypes, plot_heatmap, plot_dendrogram, generate_muller_plot
	from muller_output.generate_tables import *
	from muller_output.generate_scripts import generate_mermaid_script, generate_r_script, excecute_mermaid_script, execute_r_script
	import widgets
	from palette import generate_clade_palette

	GenotypeOptions = Any
	SortOptions = Any
	OrderClusterParameters = Any


@dataclass
class WorkflowData:
	# Used to organize the output from the workflow.
	filename: Path
	info: Optional[pandas.DataFrame]
	original_trajectories: Optional[pandas.DataFrame]
	original_genotypes: Optional[pandas.DataFrame]
	trajectories: pandas.DataFrame
	genotypes: pandas.DataFrame
	genotype_members: pandas.Series
	clusters: Dict[str, List[str]]
	genotype_options: GenotypeOptions
	sort_options: SortOptions
	cluster_options: OrderClusterParameters
	p_values: PairwiseCalculationCache
	filter_cache: List[Tuple[pandas.DataFrame, pandas.DataFrame]]
	linkage_matrix: Any
	genotype_palette_filename: Optional[Path]


class OutputFilenames:
	""" Used to organize the files generated by the workflow.
	"""

	def __init__(self, output_folder: Path, name: str, suffix = '\t'):
		self.suffix = suffix

		def check_folder(path: Union[str,Path])->Path:
			path = Path(path)
			if not path.exists():
				path.mkdir()
			return path
		output_folder = check_folder(output_folder)
		supplementary_folder = check_folder(output_folder / "supplementary-files")
		graphics_folder = check_folder(output_folder / "graphics")
		tables_folder = check_folder(output_folder / "tables")
		scripts_folder = check_folder(output_folder / "scripts")

		# General Files
		self.trajectory: Path = output_folder / (name + f'.trajectories.{suffix}')
		self.genotype: Path = output_folder / (name + f'.muller_genotypes.{suffix}')
		self.muller_plot_annotated: Path = output_folder / (name + '.muller.annotated.png')
		self.mermaid_render: Path = output_folder / (name + '.mermaid.png')
		self.genotype_plot_filtered: Path = output_folder / (name + f".filtered.png")

		# tables
		self.original_trajectory: Path = tables_folder / (name + f'.trajectories.original.{suffix}')
		self.original_genotype: Path = tables_folder / (name + f'.muller_genotypes.original.{suffix}')
		self.population: Path = tables_folder / (name + f'.ggmuller.populations.{suffix}')
		self.edges: Path = tables_folder / (name + f'.ggmuller.edges.{suffix}')
		self.muller_table: Path = tables_folder / (name + f'.muller.csv')  # This is generated in r.
		self.calculation_matrix_X = tables_folder / (name + f".calculation.matrix.distance.{suffix}")
		self.linkage_matrix_table = tables_folder / (name + f".linkagematrix.tsv")
		self.p_value: Path = tables_folder / (name + ".pvalues.tsv")
		self.calculation_matrix_p: Path = tables_folder / (name + f".calculation.matrix.pvalues.{suffix}")

		# graphics
		self.muller_plot_basic: Path = graphics_folder / (name + '.muller.basic.png')
		self.muller_plot_unannotated: Path = graphics_folder / (name + '.muller.unannotated.png')
		self.muller_plot_annotated_pdf: Path = graphics_folder / (name + '.muller.annotated.pdf')
		self.muller_plot_annotated_svg: Path = graphics_folder / (name + ".muller.annotated.svg")
		self.genotype_plot: Path = graphics_folder / (name + '.png')
		self.p_value_heatmap: Path = graphics_folder / (name + ".heatmap.pvalues.png")
		self.distance_heatmap: Path = graphics_folder / (name + f".heatmap.distance.png")
		self.linkage_plot = graphics_folder / (name + f".dendrogram.png")

		# scripts
		self.r_script: Path = scripts_folder / (name + '.r')
		self.mermaid_script: Path = scripts_folder / (name + '.mermaid.md')

		# supplementary files
		self.parameters: Path = supplementary_folder / (name + '.json')
		self.calculation_json = supplementary_folder / (name + f".calculations.json")

	@property
	def delimiter(self)->str:
		if self.suffix == '\t':
			suffix = 'tsv'
		else:
			suffix = 'csv'
		return suffix

def get_workflow_parameters(workflow_data: WorkflowData, genotype_colors = Dict[str, str]) -> Dict[str, float]:
	parameters = {
		# get_genotype_options
		'detectionCutoff':                        workflow_data.genotype_options.detection_breakpoint,
		'fixedCutoff':                            workflow_data.genotype_options.fixed_breakpoint,
		'similarityCutoff':                       workflow_data.genotype_options.similarity_breakpoint,
		'differenceCutoff':                       workflow_data.genotype_options.difference_breakpoint,
		# sort options
		'significanceCutoff':                     workflow_data.sort_options.significant_breakpoint,
		'frequencyCutoffs':                       workflow_data.sort_options.frequency_breakpoints,
		# cluster options
		'additiveBackgroundDoubleCheckCutoff':    workflow_data.cluster_options.additive_background_double_cutoff,
		'additiveBackgroundSingleCheckCutoff':    workflow_data.cluster_options.additive_background_single_cutoff,
		'subtractiveBackgroundDoubleCheckCutoff': workflow_data.cluster_options.subtractive_background_double_cutoff,
		'subtractiveBackgroundSingleCheckCutoff': workflow_data.cluster_options.subtractive_background_single_cutoff,
		'derivativeDetectionCutoff':              workflow_data.cluster_options.derivative_detection_cutoff,
		'derivativeCheckCutoff':                  workflow_data.cluster_options.derivative_check_cutoff,
		# Palette
		'genotypePalette':                        genotype_colors
	}
	return parameters


def _make_folder(folder: Path):
	if not folder.exists():
		folder.mkdir()


def generate_genotype_annotations(genotype_members: pandas.Series, info: pandas.DataFrame) -> Dict[str, List[str]]:
	gene_alias_filename = Path("/home/cld100/Documents/projects/rosch/prokka_gene_search/prokka_gene_map.txt")
	contents = gene_alias_filename.read_text().split('\n')
	lines = [line.split('\t') for line in contents if line]
	gene_aliases = {i: j for i, j in lines}
	gene_aliases['patA'] = 'dltB'
	gene_column = 'Gene'
	aa_column = 'Amino Acid'
	annotations: Dict[str, List[str]] = dict()
	for genotype_label, members in genotype_members.items():
		trajectory_labels = members.split('|')
		trajectory_subtable = info.loc[trajectory_labels]
		annotation = list()
		if gene_column in trajectory_subtable:
			gene_column_values = trajectory_subtable[gene_column]
		else:
			gene_column_values = []
		if aa_column in trajectory_subtable:
			aa_column_values = trajectory_subtable[aa_column]
		else:
			aa_column_values = []
		for i, j in itertools.zip_longest(gene_column_values, aa_column_values):
			if isinstance(i, float):
				gene = ""
			else:
				gene = i.split('<')[0]

			for k, v in gene_aliases.items():
				gene = gene.replace(k, v)

			if isinstance(j, float):  # is NAN
				effect = ""
			elif j is None:
				effect = ""
			else:
				effect = j.split('(')[0]
			annotation.append(f"{gene} {effect}")
		annotations[genotype_label] = annotation

	return annotations


def generate_output(workflow_data: WorkflowData, output_folder: Path, detection_cutoff: float, annotate_all: bool, save_pvalues: bool,
		adjust_populations: bool):

	# Set up the output folder
	filenames = OutputFilenames(output_folder, workflow_data.filename.stem)
	delimiter = filenames.delimiter


	parent_genotypes = widgets.map_trajectories_to_genotype(workflow_data.genotype_members)
	#_all_genotype_labels = sorted(set(list(workflow_data.original_genotypes.index) + list(workflow_data.genotypes.index)))

	workflow_data.original_genotypes.to_csv(str(filenames.original_genotype), sep = delimiter)
	workflow_data.genotypes.to_csv(str(filenames.genotype), sep = delimiter)
	# Generate the input tables to ggmuller
	edges_table = generate_ggmuller_edges_table(workflow_data.clusters)
	population_table = generate_ggmuller_population_table(workflow_data.genotypes, edges_table, detection_cutoff, adjust_populations)
	population_table.to_csv(str(filenames.population), sep = delimiter, index = False)
	edges_table.to_csv(str(filenames.edges), sep = delimiter, index = False)
	# Generate the palette for the praphics.
	# genotype_colors = generate_genotype_palette(_all_genotype_labels, workflow_data.genotype_palette_filename)
	genotype_colors = generate_clade_palette(edges_table)

	# Save trajectory tables, if available
	if workflow_data.original_trajectories is not None:
		workflow_data.original_trajectories.to_csv(str(filenames.original_trajectory), sep = delimiter)
	if workflow_data.trajectories is not None:
		filtered_trajectories = generate_missing_trajectories_table(workflow_data.trajectories, workflow_data.original_trajectories)
		trajectories = generate_trajectory_table(workflow_data.trajectories, parent_genotypes, workflow_data.info)
		trajectory_colors = {i: genotype_colors[parent_genotypes[i]] for i in workflow_data.trajectories.index}
		trajectories.to_csv(str(filenames.trajectory), sep = delimiter)

	# Save supplementary files
	parameters = get_workflow_parameters(workflow_data, genotype_colors)
	filenames.parameters.write_text(json.dumps(parameters, indent = 2))

	# Generate and excecute scripts
	mermaid_diagram = generate_mermaid_script(edges_table, genotype_colors)
	excecute_mermaid_script(filenames.mermaid_script, mermaid_diagram, filenames.mermaid_render)

	muller_df = generate_r_script(
		trajectory = filenames.trajectory,
		population = filenames.population,
		edges = filenames.edges,
		table_filename = filenames.muller_table,
		plot_filename = filenames.muller_plot_basic,
		script_filename = filenames.r_script,
		color_palette = genotype_colors,
		genotype_labels = population_table['Identity'].unique().tolist()
	)

	# Generate time series plots showing the mutations/genotypes over time.
	plot_genotypes(workflow_data.trajectories, workflow_data.genotypes, filenames.genotype_plot, genotype_colors, parent_genotypes)
	if workflow_data.trajectories is not None:
		plot_genotypes(filtered_trajectories, workflow_data.genotypes, filenames.genotype_plot_filtered, genotype_colors, parent_genotypes)

	# Generate muller plot, if possible
	if muller_df is not None:
		genotype_annotations = generate_genotype_annotations(workflow_data.genotype_members, workflow_data.info)
		annotated_muller_plot_filenames = [
			filenames.muller_plot_annotated,
			filenames.muller_plot_annotated_pdf,
			filenames.muller_plot_annotated_svg
		]
		generate_muller_plot(muller_df, workflow_data.trajectories, genotype_colors, annotated_muller_plot_filenames, genotype_annotations)
		generate_muller_plot(muller_df, workflow_data.trajectories, genotype_colors, filenames.muller_plot_unannotated)

	if workflow_data.linkage_matrix is not None:
		num_trajectories = len(workflow_data.trajectories)
		linkage_table = widgets.format_linkage_matrix(workflow_data.linkage_matrix, num_trajectories)
		linkage_table.to_csv(str(filenames.linkage_matrix_table), sep = delimiter, index = False)
		plot_dendrogram(workflow_data.linkage_matrix, workflow_data.p_values, filenames.linkage_plot, trajectory_colors)

	workflow_data.p_values.save(filenames.calculation_json)

	if save_pvalues:
		workflow_data.p_values.save(filenames.calculation_matrix_p)
		pvalues_matrix = workflow_data.p_values.squareform()
		plot_heatmap(pvalues_matrix, filenames.p_value_heatmap)
