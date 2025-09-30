FROM airensoft/ovenmediaengine:latest

# Copy custom configuration
COPY config/Server.xml /opt/ovenmediaengine/bin/origin_conf/Server.xml

# Expose ports
EXPOSE 9999/udp
EXPOSE 1935
EXPOSE 3333
EXPOSE 3478
EXPOSE 10000-10009/udp
EXPOSE 8081
EXPOSE 8080

# Use the default entrypoint from base image
