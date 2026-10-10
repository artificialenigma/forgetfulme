FROM caddy:2-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f
# Apply Alpine's zlib fix to the pinned upstream proxy; fail if unavailable.
RUN apk add --no-cache 'zlib>=1.3.2-r1'
