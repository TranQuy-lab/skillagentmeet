[opencode] PAGINATION — ĐÃ FIX XONG (order khách = 50, phần khác = 100, giữ nguyên 200). tsc PASS, backend build/vet/test PASS.

## 1. ORDER Ở VIEW KHÁCH HÀNG — thêm server-side pagination 50/trang
Nguyên nhân chậm: `GET /api/orders` (backend) load TOÀN BỘ đơn kèm Preload Product+Warehouse, không limit → user nhiều đơn càng chậm.
Đã sửa:
- `backend/internal/handlers/order.go` `HandleGetOrders`: thêm `page`/`page_size` (mặc định **50**, cap 100) + `search` chạy trong SQL (order_code, note, id, tên sản phẩm, tên kho) + trả `pagination {page,page_size,total_items,total_pages}` và `stats {total_orders,total_proxies}` (tính 1 query aggregate, thay cho việc FE tự đếm).
- `frontend/src/pages/user/OrderHistoryPage.tsx`: chuyển từ lọc/slice client-side sang GỌI SERVER theo trang (50/trang), search debounce 300ms, AbortController chống race, hiển thị spinner khi tải, footer dùng `serverTotal`/`serverTotalPages`.
- `frontend/src/pages/user/UserDashboardPage.tsx`: dùng `stats.total_orders`/`stats.total_proxies` thay vì đếm `data.data.length` (nếu không sửa sẽ đếm sai sau khi phân trang).

## 2. CÁC PAGINATION KHÁC = 100 (giữ nguyên chỗ đang 200 như Admin dặn)
- `MyProxiesPage.tsx`: mặc định 20 -> **100**.
- `UserOrderDetailPage.tsx`: `detailPageSize` 25 -> **100** (vẫn có tuỳ chọn All).
- `backend/internal/handlers/user_proxy_pagination.go`: mặc định page_size 50 -> **100** (cap 100).
- `admin/IntermediateProxyPanel.tsx`: page_size 50 -> **100**.
- GIỮ NGUYÊN 200: `admin/WarehouseDetailPage.tsx` (200) và `admin/ProductsPage.tsx` (200) — không đụng.

## 3. Kiểm chứng
- `npx tsc --noEmit` = PASS.
- `go build ./...` + `go vet ./internal/handlers/` + `go test ./internal/handlers/` = PASS.

## Lưu ý khi deploy
Đây là thay đổi backend + frontend; cần build lại cả hai và deploy. Không đụng file của Lead/GLM. Chờ Admin/Lead duyệt deploy. Nếu Admin muốn order ít hơn 50 (vd 20) hoặc bỏ hẳn tuỳ chọn page size ở MyProxies thì báo tôi chỉnh.
