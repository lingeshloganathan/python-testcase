import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import matplotlib.pyplot as plt
import seaborn as sns

class TestPriorityPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.label_encoder = LabelEncoder()
        
    def load_and_prepare_data(self):
        # Load test results
        test_results = pd.read_csv('../tests/results/test_results.csv')
        
        # Load user story data
        userstory_data = pd.read_csv('../backend/userstory_commit_report.csv')
        
        # Process test results
        test_results['Timestamp'] = pd.to_datetime(test_results['Timestamp'])
        test_results['Hour'] = test_results['Timestamp'].dt.hour
        test_results['DayOfWeek'] = test_results['Timestamp'].dt.dayofweek
        
        # Calculate failure rate per test
        failure_rates = test_results.groupby('Test Case ID').agg({
            'Status': lambda x: (x == 'FAILED').mean()
        }).reset_index()
        failure_rates.columns = ['Test Case ID', 'Failure_Rate']
        
        # Calculate execution frequency
        execution_counts = test_results['Test Case ID'].value_counts().reset_index()
        execution_counts.columns = ['Test Case ID', 'Execution_Count']
        
        # Merge metrics
        test_metrics = pd.merge(failure_rates, execution_counts, on='Test Case ID', how='outer')
        
        # Process user story data
        userstory_metrics = userstory_data.groupby('UserStoryID').agg({
            'CommitSHA': 'count',  # Number of commits per user story
            'FileChanged': lambda x: len(set(x))  # Number of unique files changed
        }).reset_index()
        userstory_metrics.columns = ['UserStoryID', 'Commit_Count', 'Files_Changed']
        
        # Extract user story ID from test case ID (assuming format US-XX)
        test_metrics['UserStoryID'] = test_metrics['Test Case ID'].str.extract(r'(US-\d+)')
        
        # Merge all data
        final_data = pd.merge(test_metrics, userstory_metrics, on='UserStoryID', how='left')
        
        # Fill missing values
        final_data = final_data.fillna({
            'Failure_Rate': 0,
            'Execution_Count': 0,
            'Commit_Count': 0,
            'Files_Changed': 0
        })
        
        # Calculate priority score (for training)
        final_data['Priority_Score'] = (
            final_data['Failure_Rate'] * 0.4 +
            (final_data['Execution_Count'] / final_data['Execution_Count'].max()) * 0.3 +
            (final_data['Commit_Count'] / final_data['Commit_Count'].max()) * 0.2 +
            (final_data['Files_Changed'] / final_data['Files_Changed'].max()) * 0.1
        )
        
        # Create priority categories
        final_data['Priority'] = pd.qcut(
            final_data['Priority_Score'], 
            q=3, 
            labels=['Low', 'Medium', 'High']
        )
        
        return final_data
    
    def train_model(self, data):
        # Prepare features and target
        features = ['Failure_Rate', 'Execution_Count', 'Commit_Count', 'Files_Changed']
        X = data[features]
        y = self.label_encoder.fit_transform(data['Priority'])
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Train model
        self.model.fit(X_train, y_train)
        
        # Evaluate model
        y_pred = self.model.predict(X_test)
        print("\nModel Performance:")
        print(classification_report(
            y_test, 
            y_pred, 
            target_names=self.label_encoder.classes_
        ))
        
        # Feature importance
        importance = pd.DataFrame({
            'feature': features,
            'importance': self.model.feature_importances_
        })
        importance = importance.sort_values('importance', ascending=False)
        
        # Plot feature importance
        plt.figure(figsize=(10, 6))
        sns.barplot(x='importance', y='feature', data=importance)
        plt.title('Feature Importance in Priority Prediction')
        plt.tight_layout()
        plt.savefig('feature_importance.png')
        
        return importance
    
    def predict_priority(self, test_metrics):
        """
        Predict priority for new test cases
        test_metrics should be a dictionary with:
        - Failure_Rate
        - Execution_Count
        - Commit_Count
        - Files_Changed
        """
        features = pd.DataFrame([test_metrics])
        priority_num = self.model.predict(features)[0]
        return self.label_encoder.inverse_transform([priority_num])[0]

def main():
    # Initialize predictor
    predictor = TestPriorityPredictor()
    
    # Load and prepare data
    print("Loading and preparing data...")
    data = predictor.load_and_prepare_data()
    
    # Train model
    print("\nTraining model...")
    importance = predictor.train_model(data)
    
    # Save results
    print("\nSaving results...")
    data.to_csv('test_priority_analysis.csv', index=False)
    importance.to_csv('feature_importance.csv', index=False)
    
    # Example prediction
    print("\nExample prediction:")
    test_metrics = {
        'Failure_Rate': 0.3,
        'Execution_Count': 10,
        'Commit_Count': 5,
        'Files_Changed': 3
    }
    priority = predictor.predict_priority(test_metrics)
    print(f"Predicted priority: {priority}")

if __name__ == "__main__":
    main()