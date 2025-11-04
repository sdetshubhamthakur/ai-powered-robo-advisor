#!/usr/bin/env bash
# Build script for Render

# Install dependencies
pip install -r requirements-deploy.txt

#!/usr/bin/env bash
# Build script for Render

# Install dependencies
pip install -r requirements-deploy.txt

# Always retrain model to ensure compatibility
echo "🔄 Training model with current environment..."
python train-script.py

echo "✅ Build completed successfully"

echo "Build completed successfully!"