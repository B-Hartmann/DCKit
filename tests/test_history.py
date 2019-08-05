#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test hdf5 file format"""
from __future__ import print_function

import dclab

from dckit import history

from helper_methods import retrieve_data, cleanup


def test_append_history():
    h5path = retrieve_data("rtdc_data_hdf5_rtfdc.zip")

    newlog = {"peter": "hans",
              "golem": 2}
    history.append_history(h5path, hdict=newlog)

    hlist = history.read_history(h5path)
    assert hlist[0] == newlog

    with dclab.new_dataset(h5path) as ds:
        assert "dckit-history" in ds.logs
    cleanup()


if __name__ == "__main__":
    # Run all tests
    loc = locals()
    for key in sorted(list(loc.keys())):
        if key.startswith("test_") and hasattr(loc[key], "__call__"):
            loc[key]()
