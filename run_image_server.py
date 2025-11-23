from graph.utils import load_config, ImageServer
import time

if __name__ == "__main__":
    
    config = load_config()

    # Task 5를 위한 이미지 서버 생성
    image_server = ImageServer(host_ip=config['host_ip'], 
                               port=config['port'],
                               image_directory='./results/task5')
    image_server.start()

    print("서버가 실행 중입니다. 종료하려면 Ctrl+C를 누르세요.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("서버를 종료합니다.")