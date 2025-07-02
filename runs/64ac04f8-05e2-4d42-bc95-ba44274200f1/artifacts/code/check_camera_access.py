# packages: opencv-python
import cv2

def check_camera_access() -> dict:
    """
    Checks if camera access is available using OpenCV.
    
    Returns:
        dict: A dictionary containing a boolean indicating camera availability.
    """
    try:
        # Attempt to open the default camera (index 0)
        cap = cv2.VideoCapture(0)
        # Immediately release the camera
        cap.release()
        return {"is_available": True}
    except Exception:
        # If any exception occurs, camera access is not available
        return {"is_available": False}

if __name__ == '__main__':
    result = check_camera_access()
    print(f"Camera access: {result['is_available']}")