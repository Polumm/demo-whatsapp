CREATE TABLE users (
    id UUID NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,      -- e.g. "user", "admin", etc.
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY(id)
);

CREATE TABLE conversations (
    id UUID NOT NULL UNIQUE,
    name VARCHAR(255),               -- For group chats, "Marketing Team" etc.
    type VARCHAR(50) NOT NULL,       -- e.g. "group", "direct", "channel"
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY(id)
);

CREATE TABLE users_conversation (
    id UUID NOT NULL UNIQUE,
    user_id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    role_in_convo VARCHAR(255),      -- e.g. "member", "owner", optional
    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY(id)
);

CREATE TABLE messages (
    id UUID NOT NULL UNIQUE,
    conversation_id UUID NOT NULL,
    user_id UUID NOT NULL,            -- who sent the message
    content TEXT NOT NULL,            -- store as TEXT, 255 might be too short
    type VARCHAR(50) NOT NULL,        -- "text", "image", "file", etc.
    sent_at TIMESTAMP NOT NULL,
    PRIMARY KEY(id)
);

CREATE TABLE active_user (
    id UUID NOT NULL UNIQUE,
    user_id UUID NOT NULL,
    last_online TIMESTAMP NOT NULL,
    PRIMARY KEY(id)
);

/* Foreign Keys */
ALTER TABLE active_user
ADD FOREIGN KEY(user_id) REFERENCES users(id)
ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE messages
ADD FOREIGN KEY(user_id) REFERENCES users(id)
ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE messages
ADD FOREIGN KEY(conversation_id) REFERENCES conversations(id)
ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE users_conversation
ADD FOREIGN KEY(user_id) REFERENCES users(id)
ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE users_conversation
ADD FOREIGN KEY(conversation_id) REFERENCES conversations(id)
ON UPDATE NO ACTION ON DELETE CASCADE;
