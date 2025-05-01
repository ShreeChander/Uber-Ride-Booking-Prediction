import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
# Load your cleaned dataset
df = pd.read_csv(r"D:\GUVI\Assesments\Uber demand price Prediction\data\Cleaned_booking_times.csv")

# Define features and target
X = df.drop(columns=['ride_price', 'route_from', 'route_to'])
y = df['ride_price']

# Columns for preprocessing
numerical_features = ['ride_max_persons', 'hour', 'day_of_week', 'ride_waiting_time',
                      'ride_time_minutes', 'distance_meters', 'lat_route_from',
                      'lon_route_from', 'lat_route_to', 'lon_route_to']
categorical_features = ['ride_type']

# Preprocessing and model pipeline
preprocessor = ColumnTransformer([
    ('num', StandardScaler(), numerical_features),
    ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
])

pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('model', RandomForestRegressor(n_estimators=100, random_state=42))
])

# Train model
pipeline.fit(X, y)

# Evaluate on training set
y_pred = pipeline.predict(X)
print("Model Performance:")
print("MAE:", mean_absolute_error(y, y_pred))
print("MSE:", mean_squared_error(y, y_pred))
print("R² Score:", r2_score(y, y_pred))

# --- Predict Cheapest Times ---
ride_types = ['Uber Go', 'Go Sedan']
hours = range(0, 24)
days = range(1, 8)

# Use median for other columns
medians = df[numerical_features].median()

combinations = []
for ride in ride_types:
    for h in hours:
        for d in days:
            combinations.append({
                'ride_type': ride,
                'ride_max_persons': medians['ride_max_persons'],
                'hour': h,
                'day_of_week': d,
                'ride_waiting_time': medians['ride_waiting_time'],
                'ride_time_minutes': medians['ride_time_minutes'],
                'distance_meters': medians['distance_meters'],
                'lat_route_from': medians['lat_route_from'],
                'lon_route_from': medians['lon_route_from'],
                'lat_route_to': medians['lat_route_to'],
                'lon_route_to': medians['lon_route_to']
            })

future_df = pd.DataFrame(combinations)
future_df['predicted_price'] = pipeline.predict(future_df)

# Get top 10 cheapest booking times
cheapest_times = future_df.sort_values(by='predicted_price').head(10)
print("\nTop 10 Cheapest Time Slots:")
print(cheapest_times[['ride_type', 'hour', 'day_of_week', 'predicted_price']])
# Save the trained pipeline
joblib.dump(pipeline, 'cheapest_ride.pkl')
print(" Model saved as 'cheapest_ride.pkl'")