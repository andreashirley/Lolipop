import pandas
import pytest

from muller import dataio
from muller.inheritance import LineageWorkflow
from .filenames import generic_tables

@pytest.fixture
def lineage()->LineageWorkflow:
	l = LineageWorkflow(dlimit = 0.03, flimit = 0.97, pvalue = 0.05, debug = True)
	return l

@pytest.mark.parametrize("filename", generic_tables)
def test_lineage_of_generic_datasets(lineage, filename):
	table = dataio.import_table(filename, sheet_name = "sorted", index = 'Genotype')
	expected_edges = pandas.read_excel(filename, sheet_name = "edges").set_index('Identity')['Parent'].to_dict()

	result = lineage.run(table).as_dict()

	assert result == expected_edges
