FROM hashicorp/http-echo:1.0.0 AS http_echo

FROM alpine:3.22

COPY --from=http_echo /http-echo /http-echo

EXPOSE 5678

ENTRYPOINT ["/http-echo"]
CMD ["-listen=:5678", "-text=hello from lexe"]
