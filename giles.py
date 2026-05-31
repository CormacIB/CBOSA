def generate_reduced_dataset(example_dataset, zoom):
    if zoom < 0 or zoom > 10:
        raise ValueError("Zoom should be between 0 and 10 (inclusive).")

# Calculate missing points based on zoom level
        missing_points = [i for i in range(len(example_dataset))][zoom:]

        reduced_dataset = []
        for point in example_dataset:
                if len(binary_dataset) < missing_points[0]:
                    binary_dataset.append(point)
                else:
                    break

    return reduced_dataset


