const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use(
    ["/api/**", "/static-files/**"],
    createProxyMiddleware({
      target: "http://127.0.0.1:8000",
      // Deliberately false. changeOrigin rewrites the Host header to the
      // proxy's target, which would make every request arrive at Django
      // as "127.0.0.1:8000" — and the backend resolves the tenant from
      // exactly that header. With it on, no amount of /etc/hosts setup
      // can reach a workspace locally.
      changeOrigin: false,
    })
  );
  app.use(
    ["/config.js"],
    createProxyMiddleware({
      target: "http://127.0.0.1:8000",
      changeOrigin: true,
      secure: false,
      pathRewrite: {
        "^/config.js": "/api/v1/config.js",
      },
    })
  );
  app.use(
    ["/app"],
    createProxyMiddleware({
      target: "http://127.0.0.1:3000",
      changeOrigin: true,
      pathRewrite: {
        "^/app": "/apk/akvo-mis.apk",
      },
    })
  );
  app.use(
    ["/master-data"],
    createProxyMiddleware({
      target: "http://127.0.0.1:3000",
      changeOrigin: true,
      pathRewrite: {
        "^/master-data": "/master_data/fiji-administration.csv",
      },
    })
  );
  app.use(
    ["/batch-attachments"],
    createProxyMiddleware({
      target: "http://127.0.0.1:3000",
      changeOrigin: true,
      pathRewrite: {
        "^/batch-attachments": "/batch_attachments",
      },
    })
  );
};
