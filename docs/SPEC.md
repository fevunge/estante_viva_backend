# Estante Viva — SPEC

Galeria de livros em 3D + ambiente de leitura (pt-BR, tema escuro Catppuccin com a paleta do usuário).
O chatbot foi REMOVIDO a pedido do usuário.

## Rotas

- `/` — público. Hero + galeria 3D (CSS 3D), busca e filtro por categoria. Logado: estante "Continue lendo" (progresso por livro).
- `/livro/:id` — público. Leitor PDF (react-pdf): navegação, ir para página, zoom, baixar. Painel "Caderno" à direita (abre por padrão no desktop):
  - visitante: CTA para criar conta / entrar; botão de marcador mostra toast pedindo login.
  - logado: aba Anotações (criar na página atual, filtrar "só desta página", editar, apagar, pular para a página) e aba Marcadores (marcar página com nome opcional, pular, remover); botão de marcador na barra do PDF alterna a página atual. Progresso salvo no servidor (debounce 800ms) e restaurado ao abrir.
- `/entrar` — login de leitor · `/sign-up` — criar conta (leitor ou admin) · `/admin/login` — login do admin (vai para /admin).
- `/admin` — painel do admin (CRUD de livros). Link "Painel" aparece no header só para admin.

## Auth

- Emergent-managed Clerk (e-mail + senha). Visitantes leem sem conta. Qualquer pessoa pode criar conta de leitor.
- Admin = e-mail VERIFICADO em `ADMIN_EMAIL` (<vungejuliofernando2023@gmail.com>) no primeiro login → `users.role="admin"`; demais = `member`.
- ClerkAuthProvider envolve todas as rotas, mas NÃO bloqueia páginas públicas: widgets do Clerk só renderizam via `<ClerkOnly>` quando o provider está pronto.
- Frontend envia `Authorization: Bearer <getToken()>` para `/api/me/*` e `/api/admin/*`.

## API (todas em /api)

- Público: `GET /books?q=&category=` · `GET /books/categories` · `GET /books/{id}` · `/books/{id}/pdf` · `/books/{id}/cover`
- Leitor (qualquer logado, tudo filtrado por user_id; "não é seu" = 404):
  `GET /me` · `GET|POST /me/books/{book_id}/notes` · `PUT|DELETE /me/notes/{id}` · `GET|POST /me/books/{book_id}/bookmarks` (POST idempotente por página) · `DELETE /me/bookmarks/{id}` · `GET|PUT /me/progress/{book_id}` · `GET /me/recent`
- Admin: `GET /admin/stats` · `POST /admin/books` · `PUT /admin/books/{id}` · `DELETE /admin/books/{id}` (também apaga notas/marcadores/progresso daquele livro)

## Dados (MongoDB)

- `books`, PDFs/capas no GridFS (bucket `files`), `users` {user_id, role, email, env}
- `notes` {id, user_id, book_id, page, text, created_at, updated_at}
- `bookmarks` {id, user_id, book_id, page, label, created_at} (único por user+book+page)
- `reading_progress` {user_id, book_id, page, total_pages, updated_at}
- Contas/senhas ficam no Clerk (não no banco do app).
