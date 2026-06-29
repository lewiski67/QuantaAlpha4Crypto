# Use fixed-grid out-of-sample factor evaluation

We will evaluate directional factors by allowing only a small fixed grid of trading actions, thresholds, holding horizons, and leverage values to be selected on the training set, then judge the selected strategy by validation and test performance. This deliberately limits optimizer flexibility because the main risk in crypto factor mining is overfitting noisy short-horizon data rather than failing to search a large enough strategy space.
