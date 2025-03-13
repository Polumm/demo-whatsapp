CREATE TABLE "users" (
	"id" UUID NOT NULL UNIQUE,
	"name" VARCHAR(255) NOT NULL,
	"role" VARCHAR(255) NOT NULL,
	"password" VARCHAR(255) NOT NULL,
	PRIMARY KEY("id")
);


CREATE TABLE "messages" (
	"id" UUID NOT NULL UNIQUE,
	"user_id" UUID NOT NULL,
	"conversation_id" UUID NOT NULL,
	"content" VARCHAR(255) NOT NULL,
	"sent_at" TIMESTAMP NOT NULL,
	"type" VARCHAR(255) NOT NULL,
	PRIMARY KEY("id")
);


CREATE TABLE "conversations" (
	"id" UUID NOT NULL UNIQUE,
	"name" VARCHAR(255),
	PRIMARY KEY("id")
);


CREATE TABLE "users_conversation" (
	"id" UUID NOT NULL UNIQUE,
	"user_id" UUID NOT NULL,
	"conversation_id" UUID NOT NULL,
	PRIMARY KEY("id")
);


CREATE TABLE "active_user" (
	"id" UUID NOT NULL UNIQUE,
	"user_id" UUID NOT NULL,
	"last_online" TIMESTAMP NOT NULL,
	PRIMARY KEY("id")
);


ALTER TABLE "active_user"
ADD FOREIGN KEY("id") REFERENCES "users"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "messages"
ADD FOREIGN KEY("user_id") REFERENCES "users"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "messages"
ADD FOREIGN KEY("conversation_id") REFERENCES "conversations"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "users_conversation"
ADD FOREIGN KEY("user_id") REFERENCES "users"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "users_conversation"
ADD FOREIGN KEY("conversation_id") REFERENCES "conversations"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;