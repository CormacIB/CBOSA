
binary_dataset = [
[1,2],[3,4],[5,6],7,8,9,10,11
 ]


## CORMAC 😈
def generate_reduced_dataset_simple(example_dataset, zoom):
    example_dataset = example_dataset[0::zoom+1]
    return example_dataset
print(generate_reduced_dataset_simple(binary_dataset,0))
''''
##CLAUDE
def filter_point_cloud(data, z):
    """
    data: 2D list, shape 3 x X (rows = [longitudes], [latitudes], [elevations])
    z:    zoom level, integer 0–10
    returns: 2D list, shape 3 x Y where Y = X // (1 + z)
    """
    stride = 1 + z                      # step size between selected points
    X = len(data[0])                    # total number of points
    Y = X // (1 + z)                    # target number of points

    return [row[::stride][:Y] for row in data]

##CHAT GPT!!
def zoom_filter(data, z):
    step = z + 1

    result = [[], [], []]

    for i in range(0, len(data[0]), step):
        result[0].append(data[0][i])
        result[1].append(data[1][i])
        result[2].append(data[2][i])

    return result


## GEMINI

import math

def scale_map_points(dataset, zoom_level):
    """
    Scales down a 3xX dataset based on the zoom level.
    
    Parameters:
    dataset (list of lists): A 2D array with dimensions 3 x X
    zoom_level (int): An integer z from 0 to 10
    
    Returns:
    list of lists: A 2D array with dimensions 3 x Y
    """
    # Validate zoom level
    if not (0 <= zoom_level <= 10):
        raise ValueError("Zoom level must be between 0 and 10 inclusive.")
        
    # X is the number of columns (points)
    X = len(dataset[0]) if dataset and dataset[0] else 0
    
    # Handle empty dataset edge case
    if X == 0:
        return [[], [], []]
        
    # Calculate target number of points (Y)
    Y = math.floor(X / (1 + zoom_level))
    
    # If Y is 0, return empty dimensions
    if Y == 0:
        return [[], [], []]
    
    # Select Y indices uniformly spread across the X available points
    # This ensures data-agnostic, even spatial distribution
    selected_indices = []
    if Y == 1:
        selected_indices = [0] # Default to the first point if only 1 fits
    else:
        # Calculate evenly spaced indices from 0 to X-1
        selected_indices = [round(i * (X - 1) / (Y - 1)) for i in range(Y)]
        
    # Construct the output 3 x Y array
    output_dataset = [
        [dataset[0][i] for i in selected_indices], # Row 0 (e.g., Longitude)
        [dataset[1][i] for i in selected_indices], # Row 1 (e.g., Latitude)
        [dataset[2][i] for i in selected_indices]  # Row 2 (e.g., Elevation)
    ]
    
    return output_dataset

# --- Verification with Example Data ---

# Transposing the user's example data to match the required 3 x X format
# (Rows = Dimensions, Columns = Points)
example_dataset = [
    [123456789.0123456, -654321987.6543210, 7533692187.6538646],  # Longitudes
    [-987654321.0987654, 987654321.9876543, -2147483647.0000000], # Latitudes
    [1538461538.2469132, 246913427.3747485, 1111590261.9647413]   # Elevations
]

# Test with Zoom 0 (Should return all 3 points, Y = 3 / 1 = 3)
print("Zoom 0 Result:")
print(scale_map_points(example_dataset, 0))

# Test with Zoom 1 (Should return 1 point, Y = 3 / 2 = 1.5 -> 1)
print("\nZoom 1 Result:")
print(scale_map_points(example_dataset, 1))

'''


