import os
import math
import json
import time
import redis
from confluent_kafka import Consumer
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC_INPUT = os.getenv("KAFKA_TOPIC_INPUT", "topic_raw_events")

def calculate_influence_score(followers: int, likes: int, retweets: int, replies: int, is_verified: bool) -> float:
    total_engagement = likes + retweets + replies

    log_followers = math.log10(followers + 1)
    log_engagement = math.log10(total_engagement + 1)

    verified_bonus = 1.5 if is_verified else 1.0

    influence_score = log_followers * log_engagement * verified_bonus
    return round(influence_score, 4)

def run_production():
    print(f"🔌 Khởi động Influence Worker 3 (Production Mode)...")
    print(f"Bắt nối | Redis: {REDIS_HOST}:{REDIS_PORT} | Kafka: {KAFKA_BROKER}")

    # --- Kết nối Redis ---
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        print("✅ Kết nối Redis thành công!")
    except Exception as e:
        print(f"❌ Lỗi kết nối Redis. Vui lòng bật Docker Redis: {e}")
        return

    # --- Kết nối Kafka/Redpanda ---
    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': 'influence_worker_group',
        'auto.offset.reset': 'latest' 
    })
    
    consumer.subscribe([KAFKA_TOPIC_INPUT])
    print(f"✅ Đang lắng nghe data từ topic '{KAFKA_TOPIC_INPUT}'...\n")

    try:
        while True:
            msg = consumer.poll(1.0)
            
            if msg is None: continue
            if msg.error():
                print(f"❌ Lỗi Kafka: {msg.error()}")
                continue

            try:
                event = json.loads(msg.value().decode('utf-8'))
                
                author_id = event.get("author_id")
                metrics = event.get("metrics", {})
                is_verified = event.get("is_verified", False)

                if not author_id: continue

                # Tính điểm uy tín
                score = calculate_influence_score(
                    followers=metrics.get("followers", 0),
                    likes=metrics.get("likes", 0),
                    retweets=metrics.get("retweets", 0),
                    replies=metrics.get("replies", 0),
                    is_verified=is_verified
                )

                output_data = {
                    "author_id": author_id,
                    "influence_score": score,
                    "updated_at": int(time.time())
                }

                # Lưu vào Redis với hạn sử dụng 7 ngày 
                redis_key = f"author_auth:{author_id}"
                r.set(redis_key, json.dumps(output_data), ex=604800)
                
                print(f"[{time.strftime('%H:%M:%S')}] Đã chấm điểm {author_id:<15} | Điểm: {score}")

            except json.JSONDecodeError:
                pass 
            except Exception as e:
                print(f"⚠️ Lỗi xử lý bản ghi: {e}")

    except KeyboardInterrupt:
        print("\n🛑 Tắt hệ thống an toàn...")
    finally:
        consumer.close()

if __name__ == "__main__":
    run_production()