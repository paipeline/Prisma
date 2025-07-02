# packages: opencv-python
import cv2

def start_camera_operation(camera_index: int, start_capture: bool = True) -> dict:
    """
    Initializes and starts camera operation using OpenCV VideoCapture.
    
    Args:
        camera_index (int): The index of the camera to use
        start_capture (bool): Whether to start video capture immediately. Defaults to True.
    
    Returns:
        dict: A dictionary containing the camera object, success status, and message
    """
    cap = cv2.VideoCapture(camera_index)
    success = cap.isOpened()
    message = "Camera successfully initialized" if success else "Failed to initialize camera"
    
    if success and start_capture:
        # Attempt to read a frame to start capture
        ret = cap.read()
        if not ret:
            success = False
            message = "Failed to start video capture"
    
    return {
        "camera": cap,
        "success": success,
        "message": message
    }

if __name__ == '__main__':
    # Example usage
    result = start_camera_operation(0)
    print(result)