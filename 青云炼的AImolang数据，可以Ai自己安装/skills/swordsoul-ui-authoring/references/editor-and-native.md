# Editor and native UI

## Editor screens

Use ConfigUI for repeatable editor rows and cards, but retain specialist logic for drag ordering, color picking, camera preview, import/export, and transactional save/cancel flows. Prefer a DataSource plus custom Renderer or lifecycle hook over a copied page renderer.

## Native proxies

Native ScreenProxy paths are engine-owned and are not required to appear in resource-pack JSON. Create dynamic native controls in proxy `OnCreate`, bind touch callbacks there, clear references in `OnDestroy`, and keep stack-screen opening behavior in the SWS adapter layer.

## Runtime boundary

Do not move editor or proxy business into QingYunModLibs. Only reusable rendering, binding, layout, data-source, state-store, and lifecycle primitives belong in the generic library.

