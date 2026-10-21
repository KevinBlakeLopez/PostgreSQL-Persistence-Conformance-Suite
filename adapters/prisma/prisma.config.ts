// Used only by `prisma generate`. The adapter never connects with this URL.
// The runner passes the disposable server's connection in the case message.
import { defineConfig } from 'prisma/config'

export default defineConfig({
  schema: 'schema.prisma',
  datasource: {
    url: 'postgresql://ppcs:ppcs@127.0.0.1:1/ppcs_generate_only',
  },
})
