FROM postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
# Keep PostgreSQL/gosu behavior and apply Alpine's available zlib correction.
RUN apk add --no-cache 'zlib>=1.3.2-r1'
