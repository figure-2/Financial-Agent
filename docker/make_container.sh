docker run -it \
  --name agent_container \
  -v /root/miraeasset_festa:/miraeasset_festa \
  -p 8000:8000 \
  agent_image:latest \
  bash