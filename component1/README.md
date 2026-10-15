# Component 1

Configuration, source code, notebooks, datasets, models, and experiment runs for Component 1.

## Overview

Component 1 contains the data and experimentation resources used by the glove inspection pipeline.

## Purpose

The component provides a consistent place to prepare inspection data and record experiments.

## Directory layout

- `configs/` stores component-specific configuration files.
- `datasets/` is reserved for input data and dataset metadata.
- `models/` contains model artifacts produced by experiments.
- `notebooks/` is used for exploratory analysis and prototyping.
- `runs/` keeps outputs and records from model experiments.
- `src/` contains reusable component source code and tests.

## Configuration

Keep paths and experiment settings in `configs/` so runs can be reproduced.

## Data organization

Place source images and labels under `datasets/` using a documented split structure.
