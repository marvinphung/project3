# Redis local configuration

Redis chỉ dùng cho cache/rate-limit tạm thời. AOF được bật để restart local không
làm mất state ngoài ý muốn; application vẫn không được coi Redis là source of
truth.
