require('dotenv').config();
const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder } = require('discord.js');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMessages,
  ]
});

// Enregistre la slash command /dmall
client.once('ready', async () => {
  console.log(`✅ Connecté en tant que ${client.user.tag}`);

  const commands = [
    new SlashCommandBuilder()
      .setName('dmall')
      .setDescription('Envoie un DM personnalisé à tous les membres')
      .addStringOption(option =>
        option.setName('message')
          .setDescription('Le message à envoyer (utilise {user} pour le prénom)')
          .setRequired(true)
      )
  ].map(cmd => cmd.toJSON());

  const rest = new REST({ version: '10' }).setToken(process.env.TOKEN);

  try {
    await rest.put(
      Routes.applicationCommands(client.user.id),
      { body: commands }
    );
    console.log('✅ Slash command /dmall enregistrée !');
  } catch (err) {
    console.error('Erreur enregistrement commande :', err);
  }
});

// Gestion de la commande /dmall
client.on('interactionCreate', async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  if (interaction.commandName !== 'dmall') return;

  // Vérification admin
  if (!interaction.member.permissions.has('Administrator')) {
    return interaction.reply({ content: '❌ Tu dois être administrateur !', ephemeral: true });
  }

  const customMessage = interaction.options.getString('message');

  await interaction.reply({ content: '📨 Envoi des DMs en cours...', ephemeral: true });

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

  await interaction.followUp({ content: `✅ **${success}** DMs envoyés, **${failed}** échoués (DMs fermés).`, ephemeral: true });
});

client.login(process.env.TOKEN);
