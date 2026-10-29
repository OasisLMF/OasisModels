<img src="https://oasislmf.org/packages/oasis_theme_package/themes/oasis_theme/assets/src/oasis-lmf-colour.png" alt="Oasis LMF logo" width="250"/>

# Oasis Dynamic Footprint Model Example

This is an example model which uses the dynamic footprint generation.

It's a version of the PiWind model which uses the dynamic footprint approach to build the footprint from the underlying hazard maps and event definitions based on the exposures presented


## Confluence example

Some areaperils carry hazard under several sections at once (a property reachable by two rivers);
when one event drives more than one of them, the dynamic footprint merges their intensities. The
model includes such an example: sections 3001-3003 overlap on 18 areaperils of the grid, in every
combination of one, two and three sections, each with no hazard uncertainty, the same number of
realisations everywhere, and different numbers between sections and return periods. Events 1-8
drive them.

The section rtree gives a location lying in several sections one keys row per section; OasisLMF
combines the rows of an item that differ only in `section_id` into one (`3001;3002`) when it builds
the GUL inputs. `tests/test_2` runs the 18 locations, one loss line each.

- `make_confluence_data.py` adds the example to the model data and writes `tests/test_2/location.csv`;
  its docstring describes the layout. Running it again replaces what it added and nothing else.
- `show_confluence.py [--merge max|max_independent|sum] [event_id ...]` prints the footprint the
  installed OasisLMF builds for each event at those areaperils, without a model run.

The merge rule is the `dynamic_footprint_section_merge` option (default `max`).
