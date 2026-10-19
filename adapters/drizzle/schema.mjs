// The runner's fixture tables, mapped with Drizzle's table API. The runner creates them. This adapter does not migrate.
import { integer, pgTable, serial, text } from 'drizzle-orm/pg-core'

export const item = pgTable('item', {
  id: serial('id').primaryKey(),
  name: text('name').notNull(),
  qty: integer('qty').notNull().default(0),
})

export const uniq = pgTable('uniq', {
  id: serial('id').primaryKey(),
  code: text('code').notNull().unique(),
})
