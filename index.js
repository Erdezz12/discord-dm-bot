const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder } = require('discord.js');

// Sur Railway, pas besoin de dotenv, les variables sont injectées directement
const TOKEN = process.env.TOKEN;
const SALON_AUTORISE = process.env.SALON_AUTORISE;

console.log('TOKEN chargé :', TOKEN ? 'OUI ✅' : 'NON ❌');
console.log('SALON chargé :', SALON_AUTORISE ? 'OUI ✅' : 'NON ❌');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMessages,
  ]
});

client.once('ready', async () => {
  console.log(`✅ Connecté en tant que ${client.user.tag}`);

  const commands = [
    new SlashCommandBuilder()
      .setName('dmall')
      .setDescription('Envoie un DM à tous les membres du serveur')
      .addStringOption(option =>
        option.setName('message')
          .setDescription('Le message à envoyer — utilise {user} pour le pseudo')
          .setRequired(true)
      )
  ].map(cmd => cmd.toJSON());

  const rest = new REST({ version: '10' }).setToken(TOKEN);

  try {
    await rest.put(
      Routes.applicationCommands(client.user.id),
      { body: commands }
    );
    console.log('✅ Slash command /dmall enregistrée !');
  } catch (err) {
    console.error('❌ Erreur enregistrement commande :', err);
  }
});

client.on('interactionCreate', async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  if (interaction.commandName !== 'dmall') return;

  if (interaction.channelId !== SALON_AUTORISE) {
    return interaction.reply({
      content: `❌ Cette commande est uniquement disponible dans <#${SALON_AUTORISE}> !`,
      ephemeral: true
    });
  }

  if (!interaction.member.permissions.has('Administrator')) {
    return interaction.reply({
      content: '❌ Tu dois être administrateur !',
      ephemeral: true
    });
  }

  const customMessage = interaction.options.getString('message');

  await interaction.reply({
    content: '📨 Envoi des DMs en cours...',
    ephemeral: true
  });

  const members = await interaction.guild.members.fetch();
  let success = 0;
  let failed = 0;

  for (const [, member] of members) {
    if (member.user.bot) continue;

    const personalizedMsg = customMessage
      .replace(/{user}/g, member.displayName)
      .replace(/{tag}/g, member.user.tag);

    try {
      await member.send(personalizedMsg);
      success++;
      await new Promise(r => setTimeout(r, 1000));
    } catch (err) {
      failed++;
    }
  }

  await interaction.followUp({
    content: `✅ Terminé ! **${success}** DMs envoyés, **${failed}** échoués (DMs fermés).`,
    ephemeral: true
  });
});

client.login(TOKEN);
