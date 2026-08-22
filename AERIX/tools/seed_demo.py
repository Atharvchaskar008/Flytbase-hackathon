import sys
from pathlib import Path
import uuid

# Add parent dir to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from database.session import SessionLocal, engine
from database.base import Base
from database.models.camera import Camera
from database.models.zone import Zone

def seed():
    print("Seeding demo data...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Default camera ID used by video_service
        demo_camera_id = uuid.UUID('a0000000-0000-0000-0000-000000000001')
        
        # Create Camera if not exists
        camera = db.query(Camera).filter(Camera.id == demo_camera_id).first()
        if not camera:
            camera = Camera(
                id=demo_camera_id,
                name="Main Entrance Camera (Demo)",
                location="Lobby",
                rtsp_url="rtsp://demo/live"
            )
            db.add(camera)
            print("  Created default camera")
        
        # Create a Restricted Zone in the middle of the frame
        # Mock detection 1 goes from x=120 to x=600+. It will cross x=300 to x=500.
        zone_id = uuid.UUID('b0000000-0000-0000-0000-000000000001')
        zone = db.query(Zone).filter(Zone.id == zone_id).first()
        if not zone:
            zone = Zone(
                id=zone_id,
                camera_id=demo_camera_id,
                name="Restricted Area",
                zone_type="restricted",
                polygon={
                    "points": [
                        [300, 100],
                        [500, 100],
                        [500, 400],
                        [300, 400]
                    ]
                }
            )
            db.add(zone)
            print("  Created demo zone (Restricted Area)")
        
        db.commit()
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
