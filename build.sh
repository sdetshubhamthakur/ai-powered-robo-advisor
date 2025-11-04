#!/usr/bin/env bash
# Build script for Render

# Install dependencies
pip install -r requirements-deploy.txt

#!/usr/bin/env bash
# Build script for Render deployment

echo "🔧 Installing dependencies..."
pip install -r requirements-deploy.txt

echo "🔄 Training model with production environment..."
python train-simple.py

echo "✅ Build completed successfully"
echo "📋 Verifying model file..."
if [ -f "model.joblib" ]; then
    echo "✅ Model file exists"
    ls -la model.joblib
else
    echo "❌ Model file not found!"
    exit 1
fi

echo "Build completed successfully!"
