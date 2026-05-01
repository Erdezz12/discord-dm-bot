require('dotenv').config();
const { Client, GatewayIntentBits } = require('discord.js');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,   // ⚠️ Doit être activé sur le portail
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMessages,
  ]
});

client.once('ready', () => {
  console.log(`✅ Connecté en tant que ${client.user.tag}`);
});

client.on('messageCreate', async (message) => {
  if (message.author.bot) return;
  if (!message.content.startsWith(process.env.PREFIX)) return;

  // Commande : !dm <message>
  // Tu peux utiliser {user} pour personnaliser avec le nom du membre
  const args = message.content.slice(process.env.PREFIX.length).trim().split(/ +/);
  const command = args.shift().toLowerCase();

  if (command === 'dm') {
    // Vérification : seul un admin peut utiliser cette commande
    if (!message.member.permissions.has('Administrator')) {
      return message.reply('❌ Tu dois être administrateur pour utiliser cette commande.');
    }

    const customMessage = args.join(' ');
    if (!customMessage) {
      return message.reply('❌ Usage : `!dm <ton message>` — utilise `{user}` pour le prénom du membre.');
    }

    await message.reply('📨 Envoi des DMs en cours...');

    // Récupère TOUS les membres du serveur
    const members = await message.guild.members.fetch();

    let success = 0;
    let failed = 0;

    for (const [, member] of members) {
      if (member.user.bot) continue; // Ignore les bots

      // Personnalisation : remplace {user} par le pseudo du membre
      const personalizedMsg = customMessage
        .replace(/{user}/g, member.displayName)
        .replace(/{tag}/g, member.user.tag);

      try {
        await member.send(personalizedMsg);
        success++;
        // Petite pause pour éviter le rate limit Discord
        await new Promise(r => setTimeout(r, 1000));
      } catch (err) {
        failed++; // Le membre a peut-être les DMs fermés
      }
    }

    message.channel.send(`✅ DMs envoyés : **${success}** réussis, **${failed}** échoués (DMs fermés).`);
  }
});

client.login(process.env.TOKEN);
