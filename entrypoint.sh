#!/bin/sh
# This script acts as a wrapper for the main application.
# It executes the command passed to it, and if that command
# fails (exits with a non-zero status), it runs the alerter script.

# Execute the command passed as arguments (e.g., from Docker's CMD)
echo "Wrapper: Starting application..."
"$@"

# Capture the exit code of the application
EXIT_CODE=$?

# Check if the application exited with an error
if [ $EXIT_CODE -ne 0 ]; then
    echo "Wrapper: Application crashed with exit code $EXIT_CODE. Sending alert..."
    # Run the alerter script
    python3 /app/alerter.py
    echo "Wrapper: Waiting 10 minutes before allowing a restart..."
    # Wait for 10 minutes (600 seconds)
    sleep 600
    # Exit with the original error code to signal failure to Docker
    exit $EXIT_CODE
fi

echo "Wrapper: Application exited cleanly (exit code $EXIT_CODE)."
